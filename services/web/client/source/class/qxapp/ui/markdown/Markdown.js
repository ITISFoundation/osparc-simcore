/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * @asset(marked/marked.js)
 */

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML and applies it to its value property.
 */
qx.Class.define("qxapp.ui.markdown.Markdown", {
  extend: qx.ui.basic.Label,

  /**
   * Markdown constructor. It directly accepts markdown as its first argument.
   * @param {String} markdown Plain text accepting markdown syntax. Its compiled version will be set in the value property of the label.
   */
  construct: function(markdown) {
    this.base(arguments);
    this.set({
      rich: true
    });
    this.__loadMarked = new Promise((resolve, reject) => {
      if (typeof marked === "function") {
        resolve(marked);
      } else {
        const loader = new qx.util.DynamicScriptLoader("marked/marked.js");
        loader.addListenerOnce("ready", () => {
          resolve(marked);
        }, this);
        loader.addListenerOnce("failed", e => {
          reject(Error(`Failed to load ${e.getData()}. Value couldn't be updated.`));
        });
        loader.start();
      }
    });
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
    __loadMarked: null,
    /**
     * Apply function for the markdown property. Compiles the markdown text to HTML and applies it to the value property of the label.
     * @param {String} value Plain text accepting markdown syntax.
     */
    _applyMarkdown: function(value) {
      this.__loadMarked.then(() => {
        this.setValue(marked(value));
      }).catch(error => console.error(error));
    }
  }
});
