/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * @asset(marked/marked.js)
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
          "marked/marked.js"
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
      apply: "_applyMarkdown"
    },

    noMargin: {
      check: "Boolean",
      init: true
    }
  },

  members: {
    __loadMarked: null,
    /**
     * Apply function for the markdown property. Compiles the markdown text to HTML and applies it to the value property of the label.
     * @param {String} value Plain text accepting markdown syntax.
     */
    _applyMarkdown: function(value = "") {
      this.__loadMarked.then(() => {
        const renderer = new marked.Renderer();
        const linkRenderer = renderer.link;
        renderer.link = (href, title, text) => {
          const linkColor = qx.theme.manager.Color.getInstance().resolve("link");
          const html = linkRenderer.call(renderer, href, title, text);
          // eslint-disable-next-line quotes
          const linkWithRightColor = html.replace(/^<a /, '<a style="color:'+ linkColor + ' !important"');
          return linkWithRightColor;
        };
        // eslint-disable-next-line object-curly-spacing
        const html = marked(value, { renderer });

        const safeHtml = osparc.wrapper.DOMPurify.getInstance().sanitize(html);
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
      }
    },

    __getChildrenElementHeight: function(children) {
      let height = 0;
      if (children.length) {
        for (let i=0; i<children.length; i++) {
          height += this.__getElementHeight(children[i]);
        }
      }
      return height;
    },

    __getElementHeight: function(element) {
      if (this.getNoMargin()) {
        element.style.marginTop = 0;
        element.style.marginBottom = 0;
        const size = qx.bom.element.Dimension.getSize(element);
        return size.height;
      }
      const size = qx.bom.element.Dimension.getSize(element);
      // add padding
      return size.height + 15;
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
    }
  }
});
