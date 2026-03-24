import express from "express";
import { z } from "zod";

export type Todo = {
  id: number;
  title: string;
  completed: boolean;
};

const createTodoSchema = z.object({
  title: z.string().min(1).max(120)
});

export function createApp() {
  const app = express();
  const todos: Todo[] = [];
  let nextId = 1;

  app.use(express.json());
  app.use(express.static("public"));

  app.get("/health", (_req, res) => {
    res.json({ ok: true });
  });

  app.post("/api/v1/todos", (req, res) => {
    const parsed = createTodoSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: "Validation failed",
        details: parsed.error.issues
      });
    }

    const todo: Todo = {
      id: nextId++,
      title: parsed.data.title,
      completed: false
    };
    todos.push(todo);
    return res.status(201).json({ data: todo });
  });

  app.get("/api/v1/todos", (_req, res) => {
    res.json({ data: todos });
  });

  return app;
}
