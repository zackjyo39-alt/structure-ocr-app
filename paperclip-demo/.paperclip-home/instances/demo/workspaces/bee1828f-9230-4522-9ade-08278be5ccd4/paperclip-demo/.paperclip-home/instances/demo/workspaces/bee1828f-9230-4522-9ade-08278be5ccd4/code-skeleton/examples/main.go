package main

import (
    "fmt"
    "time"
    b "paperclip-demo/.paperclip-home/instances/demo/workspaces/bee1828f-9230-4522-9ade-08278be5ccd4/code-skeleton"
)

func main() {
    m := b.NewInMemoryModel()
    rec := &b.DataRecord{
        Data: map[string]interface{}{"hello": "world"},
        CreatedAt: time.Now(),
    }
    _ = m.Save(rec)
    list, _ := m.List()
    fmt.Println("Records:", len(list))
    if len(list) > 0 {
        fmt.Printf("First: %+v\n", list[0])
    }
}
