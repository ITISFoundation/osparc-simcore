/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * @asset(marked/marked.min.js)
 */

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML and applies it to its value property.
 */
qx.Class.define("qxapp.ui.markdown.Markdown", {
  extend: qx.ui.basic.Label,

  construct: function(markdown) {
    this.base(arguments);
    this.setRich(true);
    if (markdown) {
      this.setMarkdown(markdown);
    }
  },

  properties: {
    /**
     * Holds the raw markdown text and updates the label's {@link #value} whenever new markdown arrives.
     */
    markdown: {
      check: "String",
      apply: "_applyMarkdown"
    }
  },

  members: {
    /**
     * Apply function for the markdown property. Compiles the markdown text to HTML and applies it to the value property of the label.
     * @param {String} value Plain text accepting markdown syntax.
     */
    _applyMarkdown: function(value) {
      const loader = new qx.util.DynamicScriptLoader("marked/marked.min.js");
      loader.addListenerOnce("ready", () => {
        const markdown = marked(value);
        this.setValue(markdown);
      }, this);
      loader.addListenerOnce("failed", e => {
        console.error(`Failed to load ${e.getData()}. Value couldn't be updated.`);
      });
      loader.start();
    }
  }
});
