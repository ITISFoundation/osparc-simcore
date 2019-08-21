/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * @asset(marked/marked.js)
 */

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML and applies it to its value property.
 */
qx.Class.define("qxapp.ui.markdown.Markdown", {
  extend: qx.ui.embed.Html,

  /**
   * Markdown constructor. It directly accepts markdown as its first argument.
   * @param {String} markdown Plain text accepting markdown syntax. Its compiled version will be set in the value property of the label.
   */
  construct: function(markdown) {
    this.base(arguments);

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

    this.addListenerOnce("appear", () => this.__resizeMe(), this);
    this.addListener("resize", e => this.__resizeMe(), this);
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
        const html = marked(value);
        this.setHtml(html);
        // Instead of a timer we should listen to image onload event
        qx.event.Timer.once(() => {
          this.__resizeMe();
        }, this, 2000);
        this.__resizeMe();
      }).catch(error => console.error(error));
    },

    // qx.ui.embed.html scale to content
    __resizeMe: function() {
      if (!this.getContentElement) {
        return;
      }
      const domElement = this.getContentElement().getDomElement();
      if (domElement && domElement.children && domElement.children.length) {
        let height = 0;
        for (let i=0; i<domElement.children.length; i++) {
          // add also avg padding
          height += domElement.children[i].clientHeight + 15;
        }
        this.setHeight(height);
      }
    }
  }
});
