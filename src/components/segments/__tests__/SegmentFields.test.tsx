import { useState } from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SegmentAttributeRulesField } from "../SegmentAttributeRulesField";
import { SegmentTagsField } from "../SegmentTagsField";
import { SegmentBehaviorField } from "../SegmentBehaviorField";
import { SegmentBehaviorRule, SegmentAttributeRule } from "@/types/api";

describe("Segment fields", () => {
  it("allows adding and updating attribute rules", async () => {
    const Wrapper = () => {
      const [value, setValue] = useState<SegmentAttributeRule[]>([]);
      return (
        <div>
          <SegmentAttributeRulesField value={value} onChange={setValue} />
          <div data-testid="state">{JSON.stringify(value)}</div>
        </div>
      );
    };

    render(<Wrapper />);

    const addButton = screen.getByRole("button", { name: /adicionar atributo/i });
    await userEvent.click(addButton);

    const attributeInput = screen.getByLabelText(/atributo/i);
    await userEvent.type(attributeInput, "country");

    const valuesInput = screen.getByLabelText(/valores permitidos/i);
    fireEvent.change(valuesInput, { target: { value: "BR,US" } });

    const state = screen.getByTestId("state");
    expect(state.textContent).toContain("country");
    await waitFor(() => {
      expect(state.textContent).toContain('"values":["BR","US"]');
    });
  });

  it("manages segment tags lifecycle", async () => {
    const Wrapper = () => {
      const [value, setValue] = useState<string[]>([]);
      return (
        <div>
          <SegmentTagsField value={value} onChange={setValue} />
          <div data-testid="tags-state">{JSON.stringify(value)}</div>
        </div>
      );
    };

    render(<Wrapper />);

    const input = screen.getByPlaceholderText(/ex\.: black_friday/i);
    await userEvent.type(input, "pilot");
    await userEvent.keyboard("{Enter}");

    const state = screen.getByTestId("tags-state");
    expect(state.textContent).toContain("pilot");

    const removeButton = screen.getByRole("button", { name: /remover tag pilot/i });
    await userEvent.click(removeButton);
    expect(state.textContent).toBe("[]");
  });

  it("toggles behavior switches", async () => {
    const Wrapper = () => {
      const [value, setValue] = useState<SegmentBehaviorRule>({
        requireConsent: true,
        includeOptedOut: false,
        holdoutPercentage: null,
      });
      return (
        <div>
          <SegmentBehaviorField value={value} onChange={setValue} />
          <div data-testid="behavior-state">{JSON.stringify(value)}</div>
        </div>
      );
    };

    render(<Wrapper />);

    const includeSwitch = screen.getByRole("switch", { name: /incluir contatos opt-out/i });
    await userEvent.click(includeSwitch);

    const holdoutInput = screen.getByLabelText(/percentual de holdout/i);
    await userEvent.clear(holdoutInput);
    await userEvent.type(holdoutInput, "10");

    const state = screen.getByTestId("behavior-state");
    expect(state.textContent).toContain("\"includeOptedOut\":true");
    expect(state.textContent).toContain("\"holdoutPercentage\":10");
  });
});
