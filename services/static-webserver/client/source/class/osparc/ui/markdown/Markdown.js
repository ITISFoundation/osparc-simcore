/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * @asset(marked/marked.min.js)
 * @ignore(marked)
 */

/* global marked */

/**
 * This class is just a special kind of rich label that takes markdown raw text, compiles it to HTML,
 * sanitizes it and applies it to its value property.
 */
qx.Class.define("osparc.ui.markdown.Markdown", {
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
        const loader = new qx.util.DynamicScriptLoader([
          "marked/marked.min.js"
        ]);
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
      this.setValue(markdown);
    }
    [
      "resize",
      "appear"
    ].forEach(event => {
      this.addListener(event, e => this.__resizeMe(), this);
    });

    this.setHeight(1);
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
                linkHtml += `<img src="${linkRepresentation.href}" title alt="${linkRepresentation.text}"></img>`;
              }
            }
            linkHtml += `</a>`;
            return linkHtml;
          }
        };
        marked.use({ renderer });
        // By default, Markdown requires two spaces at the end of a line or a blank line between paragraphs to produce a line break.
        // With this, a single line break (Enter) in your Markdown input will render as a <br> in HTML.
        marked.setOptions({ breaks: true }); //

        const html = marked.parse(value);

        const safeHtml = osparc.wrapper.DOMPurify.sanitize(html);
        this.setHtml(safeHtml);

        // for some reason the content is not immediately there
        qx.event.Timer.once(() => {
          this.__parseImages();
          this.__resizeMe();
        }, this, 100);

        this.__resizeMe();
      }).catch(error => console.error(error));
    },

    __parseImages: function() {
      const domElement = this.__getDomElement();
      if (domElement === null) {
        return;
      }
      const images = qx.bom.Selector.query("img", domElement);
      for (let i=0; i<images.length; i++) {
        images[i].onload = () => {
          this.__resizeMe();
        };
      }
    },

    // qx.ui.embed.html scale to content
    __resizeMe: function() {
      const domElement = this.__getDomElement();
      if (domElement === null) {
        return;
      }
      if (domElement && domElement.children) {
        const elemHeight = this.__getChildrenElementHeight(domElement.children);
        if (this.getMaxHeight() && elemHeight > this.getMaxHeight()) {
          this.setHeight(elemHeight);
        } else {
          this.setMinHeight(elemHeight);
        }

        const elemMaxWidth = this.__getChildrenElementMaxWidth(domElement.children);
        if (this.getMaxWidth() && elemMaxWidth > this.getMaxWidth()) {
          this.setWidth(elemMaxWidth);
        } else {
          this.setMinWidth(elemMaxWidth);
        }
      }
      this.fireEvent("resized");
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

    __getChildrenElementHeight: function(children) {
      let height = 0;
      if (children.length) {
        for (let i=0; i < children.length; i++) {
          height += this.__getElementHeight(children[i]);
        }
      }
      return height;
    },

    __getElementHeight: function(element) {
      if (this.getNoMargin()) {
        element.style.marginTop = 0;
        element.style.marginBottom = 0;
        const size = this.__getElementSize(element);
        return size.height;
      }
      const size = this.__getElementSize(element);
      // add padding
      return size.height + 20;
    },

    __getChildrenElementMaxWidth: function(children) {
      let maxWidth = 0;
      for (let i=0; i < children.length; i++) {
        maxWidth = Math.max(this.__getElementWidth(children[i]), maxWidth);
      }
      return maxWidth;
    },

    __getElementWidth: function(element) {
      const size = this.__getElementSize(element);
      return size.width;
    },

    __getElementSize: function(element) {
      if (
        element &&
        element.children &&
        element.children.length &&
        element.children[0].localName === "img"
      ) {
        return qx.bom.element.Dimension.getSize(element.children[0]);
      }
      return qx.bom.element.Dimension.getSize(element);
    },
  }
});
