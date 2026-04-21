package handlers

import (
	"net/http"
	"strings"

	"clawreef/internal/models"
	"clawreef/internal/services"
	"clawreef/internal/utils"

	"github.com/gin-gonic/gin"
)

type SystemSettingsHandler struct {
	systemImageSettingService services.SystemImageSettingService
}

type UpsertSystemImageSettingRequest struct {
	InstanceType string `json:"instance_type" binding:"required"`
	DisplayName  string `json:"display_name"`
	Image        string `json:"image" binding:"required"`
}

func NewSystemSettingsHandler(systemImageSettingService services.SystemImageSettingService) *SystemSettingsHandler {
	return &SystemSettingsHandler{systemImageSettingService: systemImageSettingService}
}

func (h *SystemSettingsHandler) ListSystemImageSettings(c *gin.Context) {
	settings, err := h.systemImageSettingService.List()
	if err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "System image settings retrieved successfully", gin.H{
		"items": settings,
	})
}

func (h *SystemSettingsHandler) UpsertSystemImageSetting(c *gin.Context) {
	var req UpsertSystemImageSettingRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		utils.ValidationError(c, err)
		return
	}

	setting := &models.SystemImageSetting{
		InstanceType: strings.TrimSpace(req.InstanceType),
		DisplayName:  strings.TrimSpace(req.DisplayName),
		Image:        strings.TrimSpace(req.Image),
	}

	if err := h.systemImageSettingService.Save(setting); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "System image setting saved successfully", setting)
}

func (h *SystemSettingsHandler) DeleteSystemImageSetting(c *gin.Context) {
	instanceType := c.Param("instanceType")
	if err := h.systemImageSettingService.Delete(instanceType); err != nil {
		utils.HandleError(c, err)
		return
	}

	utils.Success(c, http.StatusOK, "System image setting deleted successfully", nil)
}
