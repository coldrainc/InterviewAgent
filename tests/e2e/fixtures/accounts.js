import { randomUUID } from "node:crypto";

export function createTestAccount(prefix = "e2e") {
  const id = randomUUID().replaceAll("-", "").slice(0, 12);
  return {
    displayName: `E2E ${id.slice(0, 6)}`,
    email: `${prefix}-${id}@example.invalid`,
    password: `E2E-${id}-Pass!9`
  };
}
