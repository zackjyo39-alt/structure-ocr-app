package backbone

// Minimal skeleton for Unified Data Backbone MVP
// This file is a starting point for implementing the MVP data model and interfaces.

import "time"

type DataRecord struct {
    ID        string                 `json:"id"`
    Data      map[string]interface{} `json:"data"`
    Version   int                    `json:"version"`
    CreatedAt time.Time              `json:"created_at"`
}

type DataModel interface {
    Get(id string) (*DataRecord, error)
    Save(rec *DataRecord) error
    List() ([]*DataRecord, error)
}
