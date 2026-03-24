package backbone

// Minimal skeleton for Unified Data Backbone MVP
// This file provides a tiny in-memory model to illustrate MVP data handling
// and a simple contract for future adapters.

import (
    "errors"
    "fmt"
    "sync"
    "time"
)

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

var ErrNotFound = errors.New("not found")

// InMemoryModel is a tiny in-memory implementation of DataModel.
type InMemoryModel struct {
    mu    sync.RWMutex
    store map[string]*DataRecord
}

func NewInMemoryModel() *InMemoryModel {
    return &InMemoryModel{store: make(map[string]*DataRecord)}
}

func (m *InMemoryModel) Get(id string) (*DataRecord, error) {
    m.mu.RLock()
    defer m.mu.RUnlock()
    if rec, ok := m.store[id]; ok {
        return rec, nil
    }
    return nil, ErrNotFound
}

func (m *InMemoryModel) Save(rec *DataRecord) error {
    if rec == nil {
        return fmt.Errorf("nil record")
    }
    m.mu.Lock()
    defer m.mu.Unlock()
    if rec.ID == "" {
        rec.ID = fmt.Sprintf("rec-%d", time.Now().UnixNano())
    }
    if rec.CreatedAt.IsZero() {
        rec.CreatedAt = time.Now()
    }
    rec.Version = rec.Version + 1
    m.store[rec.ID] = rec
    return nil
}

func (m *InMemoryModel) List() ([]*DataRecord, error) {
    m.mu.RLock()
    defer m.mu.RUnlock()
    out := make([]*DataRecord, 0, len(m.store))
    for _, v := range m.store {
        out = append(out, v)
    }
    return out, nil
}
