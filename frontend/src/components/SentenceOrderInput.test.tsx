import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SentenceOrderInput } from "./SentenceOrderInput";

describe("SentenceOrderInput", () => {
  it("builds the answer word by word, in click order", async () => {
    const onChange = vi.fn();
    render(<SentenceOrderInput words={["como", "estas", "hola"]} onChange={onChange} />);

    await userEvent.click(screen.getByRole("button", { name: "hola" }));
    await userEvent.click(screen.getByRole("button", { name: "como" }));
    await userEvent.click(screen.getByRole("button", { name: "estas" }));

    expect(onChange.mock.calls.map((c) => c[0])).toEqual([
      "hola",
      "hola como",
      "hola como estas",
    ]);
  });

  it("returns a clicked built word to the available pool", async () => {
    const onChange = vi.fn();
    const { container } = render(
      <SentenceOrderInput words={["hola", "como"]} onChange={onChange} />
    );
    const [builtRow, availableRow] = Array.from(container.firstElementChild!.children);

    await userEvent.click(within(availableRow as HTMLElement).getByRole("button", { name: "hola" }));
    await userEvent.click(within(builtRow as HTMLElement).getByRole("button", { name: "hola" }));

    expect(onChange).toHaveBeenLastCalledWith("");
    expect(within(availableRow as HTMLElement).getAllByRole("button")).toHaveLength(2);
  });

  it("handles duplicate words by position, not identity", async () => {
    const onChange = vi.fn();
    const { container } = render(
      <SentenceOrderInput words={["a", "a", "b"]} onChange={onChange} />
    );
    const availableRow = container.firstElementChild!.children[1] as HTMLElement;

    await userEvent.click(within(availableRow).getAllByRole("button", { name: "a" })[0]);
    await userEvent.click(within(availableRow).getByRole("button", { name: "b" }));

    expect(onChange).toHaveBeenLastCalledWith("a b");
    expect(within(availableRow).getAllByRole("button")).toHaveLength(1); // one "a" left
  });
});
