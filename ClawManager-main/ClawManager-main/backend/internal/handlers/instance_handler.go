package handlers

import (
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"

	"clawreef/internal/models"
	"clawreef/internal/services"
	"clawreef/internal/utils"

	"github.com/gin-gonic/gin"
)

// InstanceHandler handles instance management requests
type InstanceHandler struct {
	instanceService         services.InstanceService
	accessService           *services.InstanceAccessService
	proxyService            *services.InstanceProxyService
	openClawTransferService services.OpenClawTransferService
}

// NewInstanceHandler creates a new instance handler
func NewInstanceHandler(instanceService services.InstanceService) *InstanceHandler {
	accessService := services.NewInstanceAccessService()
	return &InstanceHandler{
		instanceService:         instanceService,
		accessService:           accessService,
		proxyService:            services.NewInstanceProxyService(accessService),
		openClawTransferService: services.NewOpenClawTransferService(),
	}
}

// CreateInstanceRequest represents a create instance request
type CreateInstanceRequest struct {
	Name          string  `json:"name" binding:"required,min=3,max=50"`
	Description   *string `json:"description,omitempty"`
	Type          string  `json:"type" binding:"required,oneof=openclaw ubuntu debian centos custom webtop"`
	CPUCores      int     `json:"cpu_cores" binding:"required,min=1,max=32"`
	MemoryGB      int     `json:"memory_gb" binding:"required,min=1,max=128"`
	DiskGB        int     `json:"disk_gb" binding:"required,min=10,max=1000"`
	GPUEnabled    bool    `json:"gpu_enabled"`
	GPUCount      int     `json:"gpu_count" binding:"min=0,max=4"`
	OSType        string  `json:"os_type" binding:"required"`
	OSVersion     string  `json:"os_version" binding:"required"`
	ImageRegistry *string `json:"image_registry,omitempty"`
	ImageTag      *string `json:"image_tag,omitempty"`
	StorageClass  string  `json:"storage_class"`
}

// UpdateInstanceRequest represents an update instance request
type UpdateInstanceRequest struct {
	Name        *string `json:"name,omitempty" binding:"omitempty,min=3,max=50"`
	Description *string `json:"description,omitempty"`
}

// ListInstancesRequest represents a list instances request
type ListInstancesRequest struct {
	Page   int    `form:"page,default=1"`
	Limit  int    `form:"limit,default=20"`
	Status string `form:"status,omitempty"`
}

// ListInstances lists instances for the current user
func (h *InstanceHandler) ListInstances(c *gin.Context) {
	userID, _ := c.Get("userID")

	var req ListInstancesRequest
	if err := c.ShouldBindQuery(&req); err != nil {
		utils.ValidationError(c, err)
		return
	}

	// Calculate offset
	offset := (req.Page - 1) * req.Limit

	instances, total, err := h.instanceService.GetByUserID(userID.(int), offset, req.Limit)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	response := map[string]interface{}{
		"instances": instances,
		"total":     total,
		"page":      req.Page,
		"limit":     req.Limit,
	}

	utils.Success(c, http.StatusOK, "Instances retrieved successfully", response)
}

// CreateInstance creates a new instance
func (h *InstanceHandler) CreateInstance(c *gin.Context) {
	userID, _ := c.Get("userID")

	var req CreateInstanceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ValidationError(c, err)
		return
	}

	createReq := services.CreateInstanceRequest{
		Name:          req.Name,
		Description:   req.Description,
		Type:          req.Type,
		CPUCores:      req.CPUCores,
		MemoryGB:      req.MemoryGB,
		DiskGB:        req.DiskGB,
		GPUEnabled:    req.GPUEnabled,
		GPUCount:      req.GPUCount,
		OSType:        req.OSType,
		OSVersion:     req.OSVersion,
		ImageRegistry: req.ImageRegistry,
		ImageTag:      req.ImageTag,
		StorageClass:  req.StorageClass,
	}

	instance, err := h.instanceService.Create(userID.(int), createReq)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusCreated, "Instance created successfully", instance)
}

// GetInstance gets an instance by ID
func (h *InstanceHandler) GetInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can view)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	utils.Success(c, http.StatusOK, "Instance retrieved successfully", instance)
}

// UpdateInstance updates an instance
func (h *InstanceHandler) UpdateInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can update)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	var req UpdateInstanceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ValidationError(c, err)
		return
	}

	updateReq := services.UpdateInstanceRequest{
		Name:        req.Name,
		Description: req.Description,
	}

	if err := h.instanceService.Update(id, updateReq); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance updated successfully", nil)
}

// DeleteInstance deletes an instance
func (h *InstanceHandler) DeleteInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can delete)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	if err := h.instanceService.Delete(id); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance deleted successfully", nil)
}

// StartInstance starts an instance
func (h *InstanceHandler) StartInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can start)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	if err := h.instanceService.Start(id); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance started successfully", nil)
}

// StopInstance stops an instance
func (h *InstanceHandler) StopInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can stop)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	if err := h.instanceService.Stop(id); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance stopped successfully", nil)
}

// RestartInstance restarts an instance
func (h *InstanceHandler) RestartInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can restart)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	if err := h.instanceService.Restart(id); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance restarted successfully", nil)
}

// GetInstanceStatus gets the detailed status of an instance
func (h *InstanceHandler) GetInstanceStatus(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can view status)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	status, err := h.instanceService.GetInstanceStatus(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance status retrieved successfully", status)
}

// GenerateAccessToken generates an access token for an instance
func (h *InstanceHandler) GenerateAccessToken(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership (only admin or owner can generate access token)
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	// Check if instance is running
	if instance.Status != "running" {
		utils.Error(c, http.StatusBadRequest, "Instance is not running")
		return
	}

	// Generate proxy entry URL. The actual Service remains internal-only.
	accessURL := h.proxyService.GetProxyURL(instance.ID, "")

	if accessURL == "" {
		utils.Error(c, http.StatusServiceUnavailable, "Unable to generate access URL")
		return
	}

	// Generate access token (valid for 1 hour)
	maxAgeSeconds := int(time.Hour.Seconds())
	token, err := h.accessService.GenerateToken(
		userID.(int),
		instance.ID,
		instance.Type,
		accessURL,
		h.proxyService.GetTargetPortForInstance(instance),
		1*time.Hour,
	)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	// Store the short-lived access token in an HttpOnly cookie so iframe subresources
	// and websocket requests can reuse it without leaking the token in URLs.
	c.SetCookie(
		fmt.Sprintf("instance_access_%d", instance.ID),
		token.Token,
		maxAgeSeconds,
		fmt.Sprintf("/api/v1/instances/%d/proxy", instance.ID),
		"",
		false,
		true,
	)

	// Return token and URLs
	response := map[string]interface{}{
		"token":      token.Token,
		"access_url": accessURL,
		"proxy_url":  h.proxyService.GetProxyURL(instance.ID, token.Token),
		"expires_at": token.ExpiresAt,
	}

	utils.Success(c, http.StatusOK, "Access token generated successfully", response)
}

// AccessInstance handles instance access via token
func (h *InstanceHandler) AccessInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Validate access token
	token := c.Query("token")
	if token == "" {
		utils.Error(c, http.StatusBadRequest, "Access token required")
		return
	}

	accessToken, err := h.accessService.ValidateToken(token)
	if err != nil {
		utils.Error(c, http.StatusUnauthorized, err.Error())
		return
	}

	// Verify instance ID matches
	if accessToken.InstanceID != id {
		utils.Error(c, http.StatusForbidden, "Invalid access token for this instance")
		return
	}

	// Redirect to actual access URL
	c.Redirect(http.StatusTemporaryRedirect, accessToken.AccessURL)
}

// ForceSync manually triggers a status sync
func (h *InstanceHandler) ForceSync(c *gin.Context) {
	// Get instance ID from URL
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get instance first to check ownership
	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return
	}

	// Check ownership
	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return
	}

	// Force sync
	if err := h.instanceService.ForceSyncInstance(id); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "Instance status synced", nil)
}

// ProxyInstance proxies requests to an instance
func (h *InstanceHandler) ProxyInstance(c *gin.Context) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return
	}

	// Get token from query parameter
	token := c.Query("token")
	if token == "" {
		cookieToken, err := c.Cookie(fmt.Sprintf("instance_access_%d", id))
		if err != nil || cookieToken == "" {
			utils.Error(c, http.StatusBadRequest, "Access token required")
			return
		}
		token = cookieToken
	} else {
		// Promote the one-time query token into a cookie so iframe subresources and
		// websocket requests can reuse it without appending the token everywhere.
		c.SetCookie(
			fmt.Sprintf("instance_access_%d", id),
			token,
			int(time.Hour.Seconds()),
			fmt.Sprintf("/api/v1/instances/%d/proxy", id),
			"",
			false,
			true,
		)
	}

	// Check if it's a WebSocket upgrade request
	if strings.EqualFold(c.GetHeader("Upgrade"), "websocket") {
		err = h.proxyService.ProxyWebSocket(c.Request.Context(), id, token, c.Writer, c.Request)
		if err != nil {
			http.Error(c.Writer, err.Error(), http.StatusBadGateway)
		}
		return
	}

	// Proxy regular HTTP request
	err = h.proxyService.ProxyRequest(c.Request.Context(), id, token, c.Writer, c.Request)
	if err != nil {
		// Log the error
		fmt.Printf("Proxy error for instance %d: %v\n", id, err)

		// Return appropriate error response
		if err.Error() == "invalid token: token expired" ||
			err.Error() == "invalid token: invalid token" {
			http.Error(c.Writer, "Access token expired or invalid", http.StatusUnauthorized)
		} else if err.Error() == "token does not match instance" {
			http.Error(c.Writer, "Token does not match instance", http.StatusForbidden)
		} else {
			http.Error(c.Writer, fmt.Sprintf("Failed to proxy request: %v", err), http.StatusBadGateway)
		}
	}
}

func (h *InstanceHandler) ExportOpenClaw(c *gin.Context) {
	instance, ok := h.requireOwnedInstance(c)
	if !ok {
		return
	}

	if instance.Type != "openclaw" {
		utils.Error(c, http.StatusBadRequest, "openclaw import/export is only available for openclaw instances")
		return
	}

	if instance.Status != "running" {
		utils.Error(c, http.StatusBadRequest, "instance must be running to export .openclaw")
		return
	}

	archive, err := h.openClawTransferService.Export(c.Request.Context(), instance.UserID, instance.ID)
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	filename := fmt.Sprintf("%s.openclaw.tar.gz", sanitizeDownloadName(instance.Name))
	c.Header("Content-Type", "application/gzip")
	c.Header("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))
	c.Header("Content-Length", strconv.Itoa(len(archive)))
	c.Data(http.StatusOK, "application/gzip", archive)
}

func (h *InstanceHandler) ImportOpenClaw(c *gin.Context) {
	instance, ok := h.requireOwnedInstance(c)
	if !ok {
		return
	}

	if instance.Type != "openclaw" {
		utils.Error(c, http.StatusBadRequest, "openclaw import/export is only available for openclaw instances")
		return
	}

	if instance.Status != "running" {
		utils.Error(c, http.StatusBadRequest, "instance must be running to import .openclaw")
		return
	}

	fileHeader, err := c.FormFile("file")
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "file is required")
		return
	}

	file, err := fileHeader.Open()
	if err != nil {
		utils.HandleError(c, err)
		return
	}
	defer file.Close()

	if err := h.openClawTransferService.Import(c.Request.Context(), instance.UserID, instance.ID, io.LimitReader(file, 512<<20)); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "OpenClaw workspace imported successfully", nil)
}

func (h *InstanceHandler) requireOwnedInstance(c *gin.Context) (*models.Instance, bool) {
	idStr := c.Param("id")
	id, err := strconv.Atoi(idStr)
	if err != nil {
		utils.Error(c, http.StatusBadRequest, "Invalid instance ID")
		return nil, false
	}

	instance, err := h.instanceService.GetByID(id)
	if err != nil {
		utils.HandleError(c, err)
		return nil, false
	}

	if instance == nil {
		utils.Error(c, http.StatusNotFound, "Instance not found")
		return nil, false
	}

	userID, _ := c.Get("userID")
	userRole, _ := c.Get("userRole")
	if userRole != "admin" && instance.UserID != userID.(int) {
		utils.Error(c, http.StatusForbidden, "Access denied")
		return nil, false
	}

	return instance, true
}

func sanitizeDownloadName(name string) string {
	name = strings.TrimSpace(name)
	if name == "" {
		return "openclaw-workspace"
	}

	replacer := strings.NewReplacer("\\", "-", "/", "-", ":", "-", "*", "-", "?", "-", "\"", "-", "<", "-", ">", "-", "|", "-")
	name = replacer.Replace(name)
	name = strings.ReplaceAll(name, " ", "-")
	return name
}
