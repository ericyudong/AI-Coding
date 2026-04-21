package repository

import (
	"fmt"
	"time"

	"clawreef/internal/models"

	"github.com/upper/db/v4"
)

// SystemImageSettingRepository defines repository operations for runtime image settings.
type SystemImageSettingRepository interface {
	List() ([]models.SystemImageSetting, error)
	GetByInstanceType(instanceType string) (*models.SystemImageSetting, error)
	Upsert(setting *models.SystemImageSetting) error
	DeleteByInstanceType(instanceType string) error
}

type systemImageSettingRepository struct {
	sess db.Session
}

// NewSystemImageSettingRepository creates a new repository and ensures the table exists.
func NewSystemImageSettingRepository(sess db.Session) SystemImageSettingRepository {
	repo := &systemImageSettingRepository{sess: sess}
	repo.ensureTable()
	return repo
}

func (r *systemImageSettingRepository) ensureTable() {
	const query = `
CREATE TABLE IF NOT EXISTS system_image_settings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  instance_type VARCHAR(50) NOT NULL UNIQUE,
  display_name VARCHAR(255) NOT NULL,
  image VARCHAR(500) NOT NULL,
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_instance_type (instance_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
`

	if _, err := r.sess.SQL().Exec(query); err != nil {
		panic(fmt.Errorf("failed to ensure system_image_settings table: %w", err))
	}

	var count int
	row, err := r.sess.SQL().QueryRow(`
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'system_image_settings'
  AND column_name = 'is_enabled'
`)
	if err != nil {
		panic(fmt.Errorf("failed to inspect system_image_settings columns: %w", err))
	}
	if err := row.Scan(&count); err != nil {
		panic(fmt.Errorf("failed to scan system_image_settings column count: %w", err))
	}

	if count == 0 {
		if _, err := r.sess.SQL().Exec("ALTER TABLE system_image_settings ADD COLUMN is_enabled BOOLEAN NOT NULL DEFAULT TRUE"); err != nil {
			panic(fmt.Errorf("failed to ensure system_image_settings.is_enabled column: %w", err))
		}
	}
}

func (r *systemImageSettingRepository) List() ([]models.SystemImageSetting, error) {
	var settings []models.SystemImageSetting
	if err := r.sess.Collection("system_image_settings").Find().OrderBy("instance_type").All(&settings); err != nil {
		return nil, fmt.Errorf("failed to list system image settings: %w", err)
	}
	return settings, nil
}

func (r *systemImageSettingRepository) GetByInstanceType(instanceType string) (*models.SystemImageSetting, error) {
	var setting models.SystemImageSetting
	err := r.sess.Collection("system_image_settings").Find(db.Cond{"instance_type": instanceType}).One(&setting)
	if err != nil {
		if err == db.ErrNoMoreRows {
			return nil, nil
		}
		return nil, fmt.Errorf("failed to get system image setting: %w", err)
	}
	return &setting, nil
}

func (r *systemImageSettingRepository) Upsert(setting *models.SystemImageSetting) error {
	existing, err := r.GetByInstanceType(setting.InstanceType)
	if err != nil {
		return err
	}

	now := time.Now()
	if existing == nil {
		if !setting.IsEnabled {
			setting.IsEnabled = false
		}
		setting.CreatedAt = now
		setting.UpdatedAt = now
		if _, err := r.sess.Collection("system_image_settings").Insert(setting); err != nil {
			return fmt.Errorf("failed to create system image setting: %w", err)
		}
		return nil
	}

	existing.DisplayName = setting.DisplayName
	existing.Image = setting.Image
	existing.IsEnabled = setting.IsEnabled
	existing.UpdatedAt = now
	if err := r.sess.Collection("system_image_settings").Find(db.Cond{"id": existing.ID}).Update(existing); err != nil {
		return fmt.Errorf("failed to update system image setting: %w", err)
	}
	return nil
}

func (r *systemImageSettingRepository) DeleteByInstanceType(instanceType string) error {
	existing, err := r.GetByInstanceType(instanceType)
	if err != nil {
		return err
	}
	if existing == nil {
		return nil
	}
	if err := r.sess.Collection("system_image_settings").Find(db.Cond{"id": existing.ID}).Delete(); err != nil {
		return fmt.Errorf("failed to delete system image setting: %w", err)
	}
	return nil
}
