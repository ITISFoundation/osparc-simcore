/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odei maiz)
 */

/**
 * @asset(hint/hint.css)
 */

qx.Class.define("osparc.ui.basic.FloatingHelper", {
  extend: qx.ui.core.Widget,
  include: [qx.ui.core.MRemoteChildrenHandling, qx.ui.core.MRemoteLayoutHandling],

  construct: function(element) {
    this.base(arguments);
    this.set({
      backgroundColor: "transparent",
      visibility: "excluded",
      zIndex: 110000
    });

    const hintCssUri = qx.util.ResourceManager.getInstance().toUri("hint/hint.css");
    qx.module.Css.includeStylesheet(hintCssUri);

    this.__buildWidget();
    qx.core.Init.getApplication().getRoot().add(this);

    if (element) {
      if (element.getContentElement().getDomElement() == null) {
        element.addListenerOnce("appear", () => this.setElement(element), this);
      } else {
        this.setElement(element);
      }
    }

    this.setLayout(new qx.ui.layout.Basic());
  },

  statics: {
    ORIENTATION: {
      TOP: 0,
      RIGHT: 1,
      BOTTOM: 2,
      LEFT: 3
    },

    textToOrientation: function(text) {
      if (Object.keys(osparc.ui.basic.FloatingHelper.ORIENTATION).includes(text.toUpperCase())) {
        return osparc.ui.basic.FloatingHelper.ORIENTATION[text.toUpperCase()];
      }
      return null;
    }
  },

  properties: {
    element: {
      check: "qx.ui.core.Widget",
      apply: "__applyElement"
    },

    orientation: {
      check: "Integer",
      nullable: false,
      init: 2,
      apply: "__applyOrientation"
    },

    caretSize: {
      check: "Integer",
      nullable: false,
      init: 5
    },

    active: {
      check: "Boolean",
      nullable: false,
      init: false
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "hint-container":
          control = new qx.ui.container.Composite().set({
            appearance: "hint",
            backgroundColor: "node-selected-background"
          });
          break;
        case "caret":
          control = new qx.ui.container.Composite().set({
            backgroundColor: "transparent"
          });
          control.getContentElement().addClass("hint");
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildWidget: function() {
      this._removeAll();

      const hintContainer = this.getChildControl("hint-container");
      const caret = this.getChildControl("caret");
      caret.getContentElement().removeClass("hint-top");
      caret.getContentElement().removeClass("hint-right");
      caret.getContentElement().removeClass("hint-bottom");
      caret.getContentElement().removeClass("hint-left");
      switch (this.getOrientation()) {
        case this.self().ORIENTATION.TOP:
        case this.self().ORIENTATION.LEFT: {
          caret.getContentElement().addClass(this.getOrientation() === this.self().ORIENTATION.LEFT ? "hint-left" : "hint-top");
          this._setLayout(this.getOrientation() === this.self().ORIENTATION.LEFT ? new qx.ui.layout.HBox() : new qx.ui.layout.VBox());
          this._add(hintContainer, {
            flex: 1
          });
          this._add(caret);
          break;
        }
        case this.self().ORIENTATION.RIGHT:
        case this.self().ORIENTATION.BOTTOM: {
          caret.getContentElement().addClass(this.getOrientation() === this.self().ORIENTATION.RIGHT ? "hint-right" : "hint-bottom");
          this._setLayout(this.getOrientation() === this.self().ORIENTATION.RIGHT ? new qx.ui.layout.HBox() : new qx.ui.layout.VBox());
          this._add(caret);
          this._add(hintContainer, {
            flex: 1
          });
          break;
        }
      }
      const caretSize = this.getCaretSize();
      switch (this.getOrientation()) {
        case this.self().ORIENTATION.RIGHT:
        case this.self().ORIENTATION.LEFT:
          caret.setHeight(0);
          caret.setWidth(caretSize);
          break;
        case this.self().ORIENTATION.TOP:
        case this.self().ORIENTATION.BOTTOM:
          caret.setWidth(0);
          caret.setHeight(caretSize);
          break;
      }
    },

    __updatePosition: function() {
      if (this.isPropertyInitialized("element") && this.getElement().getContentElement()) {
        const element = this.getElement().getContentElement()
          .getDomElement();
        const {
          top,
          left
        } = qx.bom.element.Location.get(element);
        const {
          width,
          height
        } = qx.bom.element.Dimension.getSize(element);
        const selfBounds = this.getHintBounds();
        let properties = {};
        switch (this.getOrientation()) {
          case this.self().ORIENTATION.TOP:
            properties.top = top - selfBounds.height;
            properties.left = Math.floor(left + (width - selfBounds.width) / 2);
            break;
          case this.self().ORIENTATION.RIGHT:
            properties.top = Math.floor(top + (height - selfBounds.height) / 2);
            properties.left = left + width;
            break;
          case this.self().ORIENTATION.BOTTOM:
            properties.top = top + height;
            properties.left = Math.floor(left + (width - selfBounds.width) / 2);
            break;
          case this.self().ORIENTATION.LEFT:
            properties.top = Math.floor(top + (height - selfBounds.height) / 2);
            properties.left = left - selfBounds.width;
            break;
        }
        this.setLayoutProperties(properties);
      }
    },

    getHintBounds: function() {
      return this.getBounds() || this.getSizeHint();
    },

    __applyOrientation: function() {
      this.__buildWidget();
      this.__updatePosition();
    },

    // overwritten
    getChildrenContainer: function() {
      return this.getChildControl("hint-container");
    },

    __applyElement: function(element, oldElement) {
      if (oldElement) {
        oldElement.removeListener("appear", this._elementAppearDisappearHandler);
        oldElement.removeListener("disappear", this._elementAppearDisappearHandler);
        this.__removeListeners(["move", "resize"]);
        this.__removeListeners(["scrollX", "scrollY"], true);
      }
      if (element) {
        const isElementVisible = qx.ui.core.queue.Visibility.isVisible(element);
        if (isElementVisible && this.isActive()) {
          this.show();
        }
        element.addListener("appear", this._elementAppearDisappearHandler, this);
        element.addListener("disappear", this._elementAppearDisappearHandler, this);
        this.__addListeners(["move", "resize"]);
        this.__addListeners(["scrollX", "scrollY"], true);
      } else {
        this.exclude();
      }
    },

    __addListeners: function(events, skipThis = false) {
      let widget = skipThis ? this.getElement().getLayoutParent() : this.getElement();
      while (widget && widget !== qx.core.Init.getApplication().getRoot()) {
        events.forEach(e => {
          if (qx.util.OOUtil.supportsEvent(widget, e)) {
            widget.addListener(e, this.__elementVisibilityHandler, this);
          }
        });
        widget = widget.getLayoutParent();
      }
    },

    __removeListeners: function(events, skipThis = false) {
      let widget = skipThis ? this.getElement().getLayoutParent() : this.getElement();
      while (widget && widget !== qx.core.Init.getApplication().getRoot()) {
        events.forEach(e => {
          if (qx.util.OOUtil.supportsEvent(widget, e)) {
            widget.removeListener(e, this.__elementVisibilityHandler);
          }
        });
        widget = widget.getLayoutParent();
      }
    },

    _elementAppearDisappearHandler: function(e) {
      this.__elementVisibilityHandler(e);
    },

    __elementVisibilityHandler: function(e) {
      switch (e.getType()) {
        case "appear":
          if (this.isActive()) {
            this.show();
          }
          this.__updatePosition();
          break;
        case "disappear":
          this.exclude();
          break;
        case "move":
        case "resize":
        case "scrollX":
        case "scrollY":
          setTimeout(() => this.__updatePosition(), 50); // Hacky: Execute async and give some time for the relevant properties to be set
          break;
      }
    },

    // overridden
    _applyVisibility: function(ne, old) {
      this.base(arguments, ne, old);
      this.__updatePosition();
    }
  }
});
