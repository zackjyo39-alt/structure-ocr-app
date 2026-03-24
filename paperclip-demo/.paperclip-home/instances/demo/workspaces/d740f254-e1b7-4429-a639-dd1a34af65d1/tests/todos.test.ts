import request from "supertest";
import { describe, expect, it } from "vitest";
import { createApp } from "../src/app.js";

describe("todos API", () => {
  it("creates and lists todos", async () => {
    const app = createApp();

    const createRes = await request(app)
      .post("/api/v1/todos")
      .send({ title: "Ship MVP" });

    expect(createRes.status).toBe(201);
    expect(createRes.body.data.title).toBe("Ship MVP");

    const listRes = await request(app).get("/api/v1/todos");

    expect(listRes.status).toBe(200);
    expect(listRes.body.data).toHaveLength(1);
  });

  it("validates title", async () => {
    const app = createApp();
    const res = await request(app).post("/api/v1/todos").send({ title: "" });
    expect(res.status).toBe(400);
  });
});
