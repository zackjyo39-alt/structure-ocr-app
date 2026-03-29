package backbone

import "testing"

func TestInMemoryModel_VersionIncrement(t *testing.T) {
    m := NewInMemoryModel()
    rec := &DataRecord{Data: map[string]interface{}{"k": "v"}}
    if err := m.Save(rec); err != nil {
        t.Fatalf("save error: %v", err)
    }
    rec2 := &DataRecord{Data: map[string]interface{}{"k": "v2"}}
    if err := m.Save(rec2); err != nil {
        t.Fatalf("second save error: %v", err)
    }
    list, err := m.List()
    if err != nil {
        t.Fatalf("list error: %v", err)
    }
    if len(list) < 2 {
        t.Fatalf("expected at least 2 records, got %d", len(list))
    }
    if list[0].Version == list[1].Version {
        t.Fatalf("expected version to advance between saves: %d vs %d", list[0].Version, list[1].Version)
    }
}
