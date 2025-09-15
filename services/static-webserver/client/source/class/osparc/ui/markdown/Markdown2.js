/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * @asset(marked/marked.min.js)
 * @assert(markdown.css)
 * @ignore(marked)
 */

/* global marked */

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML,
 * sanitizes it and applies it to its value property.
 */
qx.Class.define("osparc.ui.markdown.Markdown2", {
  extend: qx.ui.embed.Html,

  /**
   * Markdown constructor. It directly accepts markdown as its first argument.
   * @param {String} markdown Plain text accepting markdown syntax. Its compiled version will be set in the value property of the label.
   */
  construct: function(markdown) {
    this.base(arguments);

    this.set({
      allowGrowX: true,
      allowGrowY: true,
      overflowX: "hidden",
      overflowY: "hidden",
    });

    const markdownCssUri = qx.util.ResourceManager.getInstance().toUri("markdown/markdown.css");
    qx.module.Css.includeStylesheet(markdownCssUri);

    this.__loadMarked = new Promise((resolve, reject) => {
      if (typeof marked === "function") {
        resolve(marked);
      } else {
        const loader = new qx.util.DynamicScriptLoader([
          "marked/marked.min.js"
        ]);
        loader.addListenerOnce("ready", () => resolve(marked), this);
        loader.addListenerOnce("failed", e =>
          reject(Error(`Failed to load ${e.getData()}`))
        );
        loader.start();
      }
    });

    if (markdown) {
      this.setValue(markdown);
    }

    this.addListenerOnce("appear", () => {
      this.getContentElement().addClass("osparc-markdown");
    });
  },

  properties: {
    /**
     * Holds the raw markdown text and updates the label's {@link #value} whenever new markdown arrives.
     */
    value: {
      check: "String",
      apply: "__applyMarkdown"
    },

    noMargin: {
      check: "Boolean",
      init: false
    }
  },

  events: {
    "resized": "qx.event.type.Event",
  },

  members: {
    __loadMarked: null,
    /**
     * Apply function for the markdown property. Compiles the markdown text to HTML and applies it to the value property of the label.
     * @param {String} value Plain text accepting markdown syntax.
     */
    __applyMarkdown: function(value = "") {
      this.__loadMarked.then(() => {
        const renderer = {
          link(link) {
            const linkColor = qx.theme.manager.Color.getInstance().resolve("link");
            let linkHtml = `<a href="${link.href}" title="${link.title || ""}" style="color: ${linkColor};">`
            if (link.tokens && link.tokens.length) {
              const linkRepresentation = link.tokens[0];
              if (linkRepresentation.type === "text") {
                linkHtml += linkRepresentation.text;
              } else if (linkRepresentation.type === "image") {
                linkHtml += `<img src="${linkRepresentation.href}" tile alt="${linkRepresentation.text}"></img>`;
              }
            }
            linkHtml += `</a>`;
            return linkHtml;
          }
        };
        marked.use({ renderer });
        // By default, Markdown requires two spaces at the end of a line or a blank line between paragraphs to produce a line break.
        // With this, a single line break (Enter) in your Markdown input will render as a <br> in HTML.
        marked.setOptions({ breaks: true });

        const html = marked.parse(value);

        const safeHtml = osparc.wrapper.DOMPurify.getInstance().sanitize(html);

        this.setHtml(safeHtml);

        // for some reason the content is not immediately there
        qx.event.Timer.once(() => {
          this.__resizeMe();
        }, this, 100);

        this.__resizeMe();
      }).catch(error => console.error(error));
    },

    __getDomElement: function() {
      if (!this.getContentElement || this.getContentElement() === null) {
        return null;
      }
      const domElement = this.getContentElement().getDomElement();
      if (domElement) {
        return domElement;
      }
      return null;
    },

    // qx.ui.embed.html scale to content
    __resizeMe: function() {
      const domElement = this.__getDomElement();
      if (domElement === null) {
        return;
      }
      this.setHeight(null);            // let it auto-size
      this.setMinHeight(domElement.scrollHeight); // so layout respects full content
    },
  }
});
