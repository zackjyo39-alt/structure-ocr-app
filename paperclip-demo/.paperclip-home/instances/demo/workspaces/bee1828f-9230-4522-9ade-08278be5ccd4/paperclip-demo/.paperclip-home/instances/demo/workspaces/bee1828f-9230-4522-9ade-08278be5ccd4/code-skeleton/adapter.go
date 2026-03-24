package backbone

// Simple adapters to illustrate data source integration.

type SourceAAdapter struct {
    Model DataModel
}

type SourceBAdapter struct {
    Model DataModel
}

func NewSourceAAdapter(m DataModel) *SourceAAdapter {
    return &SourceAAdapter{Model: m}
}

func NewSourceBAdapter(m DataModel) *SourceBAdapter {
    return &SourceBAdapter{Model: m}
}

func (a *SourceAAdapter) Get(id string) (*DataRecord, error) {
    return a.Model.Get(id)
}

func (b *SourceBAdapter) Get(id string) (*DataRecord, error) {
    return b.Model.Get(id)
}
