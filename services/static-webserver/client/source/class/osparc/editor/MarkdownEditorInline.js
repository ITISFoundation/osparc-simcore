/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.editor.MarkdownEditorInline", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base(arguments);

    this.setLayout(new qx.ui.layout.VBox(8));

    this.getChildControl("toolbar");
    this.getChildControl("text-area");
  },

  statics: {
    __createToolbarBtn(label, tooltip, fn) {
      const b = new qx.ui.toolbar.Button(label);
      b.setToolTipText(tooltip);
      b.addListener("execute", fn);
      return b;
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "toolbar":
          control = this.__createToolbar();
          this.add(control);
          break;
        case "text-area":
          control = new qx.ui.form.TextArea().set({
            wrap: true,
          });
          this.add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    getValue: function() {
      return this.__area.getValue() || "";
    },

    setValue: function(v) {
      this.__area.setValue(v || "");
    },

    __createToolbar: function() {
      const tb = new qx.ui.toolbar.ToolBar();
      tb.add(this.self().__createToolbarBtn("B", "Bold", () => this.__wrapSelection("**", "**", "bold text")));
      tb.add(this.self().__createToolbarBtn("I", "Italic", () => this.__wrapSelection("*", "*", "italic text")));
      tb.add(this.self().__createToolbarBtn("Link", "Insert link", () => this.__insertLink()));
      tb.add(new qx.ui.toolbar.Separator());
      tb.add(this.self().__createToolbarBtn("• List", "Bulleted list", () => this.__prefixLines("- ")));
      tb.add(this.self().__createToolbarBtn("1. List", "Numbered list", () => this.__numberLines()));
      return tb;
    },

    __getDomTextArea() {
      // Access underlying DOM textarea for selectionStart/End
      const el = this.__area.getContentElement().getDomElement();
      // In qooxdoo TextArea, dom element is <textarea>
      return el;
    },

    __getSelection() {
      const dom = this.__getDomTextArea();
      if (!dom) return null;

      const textArea = this.getChildControl("text-area");
      const value = textArea.getValue() || "";
      const start = dom.selectionStart != null ? dom.selectionStart : value.length;
      const end = dom.selectionEnd != null ? dom.selectionEnd : value.length;

      return { textArea, value, start, end };
    },

    __applyEdit(newValue, newStart, newEnd) {
      const textArea = this.getChildControl("text-area");
      textArea.setValue(newValue);
      textArea.focus();

      if (newStart != null && newEnd != null) {
        qx.event.Timer.once(() => {
          const dom = this.__getDomTextArea();
          if (!dom) return;
          dom.selectionStart = newStart;
          dom.selectionEnd = newEnd;
        }, this, 0);
      }
    },

    __wrapSelection(prefix, suffix, placeholder) {
      const sel = this.__getSelection();
      if (!sel) return;

      const { value, start, end } = sel;
      const selected = value.substring(start, end) || placeholder;

      const nextValue =
        value.substring(0, start) +
        prefix + selected + suffix +
        value.substring(end);

      const newStart = start + prefix.length;
      const newEnd = newStart + selected.length;

      this.__applyEdit(nextValue, newStart, newEnd);
    },

    __insertLink() {
      const sel = this.__getSelection();
      if (!sel) return;

      const { value, start, end } = sel;
      const selected = value.substring(start, end) || "link text";
      const snippet = `[${selected}](https://example.com)`;

      const nextValue =
        value.substring(0, start) +
        snippet +
        value.substring(end);

      const urlStart = start + snippet.indexOf("(") + 1;
      const urlEnd = start + snippet.indexOf(")");

      this.__applyEdit(nextValue, urlStart, urlEnd);
    },

    __prefixLines(prefix) {
      const sel = this.__getSelection();
      if (!sel) return;

      const { value, start, end } = sel;

      // Expand selection to full lines
      const lineStart = value.lastIndexOf("\n", start - 1) + 1;
      const lineEndIdx = value.indexOf("\n", end);
      const lineEnd = lineEndIdx === -1 ? value.length : lineEndIdx;

      const block = value.substring(lineStart, lineEnd);
      const updated = block
        .split("\n")
        .map(line => line.trim().length ? prefix + line : line)
        .join("\n");

      const nextValue =
        value.substring(0, lineStart) +
        updated +
        value.substring(lineEnd);

      this.__applyEdit(nextValue);
    },

    __numberLines() {
      const sel = this.__getSelection();
      if (!sel) return;

      const { value, start, end } = sel;

      const lineStart = value.lastIndexOf("\n", start - 1) + 1;
      const lineEndIdx = value.indexOf("\n", end);
      const lineEnd = lineEndIdx === -1 ? value.length : lineEndIdx;

      const lines = value.substring(lineStart, lineEnd).split("\n");
      let n = 1;

      const updated = lines.map(line => {
        if (!line.trim().length) return line;
        return `${n++}. ${line}`;
      }).join("\n");

      const nextValue =
        value.substring(0, lineStart) +
        updated +
        value.substring(lineEnd);

      this.__applyEdit(nextValue);
    }
  }
});
