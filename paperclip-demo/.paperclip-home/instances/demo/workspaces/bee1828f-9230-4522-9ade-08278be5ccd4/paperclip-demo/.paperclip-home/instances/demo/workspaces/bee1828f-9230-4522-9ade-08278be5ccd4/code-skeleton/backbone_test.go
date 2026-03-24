package backbone

import (
    "testing"
)

func TestInMemoryModel_SaveAndList(t *testing.T) {
    m := NewInMemoryModel()
    r := &DataRecord{Data: map[string]interface{}{"k":"v"}}
    if err := m.Save(r); err != nil {
        t.Fatalf("save error: %v", err)
    }
    records, err := m.List()
    if err != nil {
        t.Fatalf("list error: %v", err)
    }
    if len(records) == 0 {
        t.Fatalf("expected at least 1 record, got 0")
    }
}
