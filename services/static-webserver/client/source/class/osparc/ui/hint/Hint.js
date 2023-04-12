/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * @asset(hint/hint.css)
 */

qx.Class.define("osparc.ui.hint.Hint", {
  extend: qx.ui.core.Widget,
  include: [qx.ui.core.MRemoteChildrenHandling, qx.ui.core.MRemoteLayoutHandling],

  construct: function(element, text) {
    this.base(arguments);
    this.set({
      backgroundColor: "transparent",
      visibility: "excluded",
      zIndex: 110000
    });

    const hintCssUri = qx.util.ResourceManager.getInstance().toUri("hint/hint.css");
    qx.module.Css.includeStylesheet(hintCssUri);

    this._buildWidget();
    qx.core.Init.getApplication().getRoot().add(this);

    if (element) {
      if (element.getContentElement().getDomElement() == null) {
        element.addListenerOnce("appear", () => this.setElement(element), this);
      } else {
        this.setElement(element);
      }
    }

    this.setLayout(new qx.ui.layout.Basic());
    const label = this.getChildControl("label");
    this.add(label);
    if (text === undefined) {
      text = "";
    }
    label.setValue(text);
  },

  statics: {
    orientation:{
      TOP: 0,
      RIGHT: 1,
      BOTTOM: 2,
      LEFT: 3
    }
  },

  properties: {
    element: {
      check: "qx.ui.core.Widget",
      apply: "_applyElement"
    },

    active: {
      check: "Boolean",
      nullable: false,
      init: false
    },

    orientation: {
      check: "Integer",
      nullable: false,
      init: 2,
      apply: "_applyOrientation"
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
        case "label":
          control = new qx.ui.basic.Label().set({
            rich: true,
            maxWidth: 200
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    attachShowHideHandlers: function() {
      if (this.getElement()) {
        const element = this.getElement();

        const showHint = () => this.show();
        const hideHint = () => this.exclude();
        const tapListener = e => {
          // Make hint "modal" when parent element is clicked
          if (osparc.utils.Utils.isMouseOnElement(this, e)) {
            return;
          }
          hideHint();
          document.removeEventListener("mousedown", tapListener);
          element.addListener("mouseover", showHint);
          element.addListener("mouseout", hideHint);
        };

        element.addListener("mouseover", showHint);
        element.addListener("mouseout", hideHint);
        element.addListener("tap", () => {
          showHint();
          document.addEventListener("mousedown", tapListener);
          element.removeListener("mouseover", showHint);
          element.removeListener("mouseout", hideHint);
        }, this);
      }
    },

    _buildWidget: function() {
      this._removeAll();

      const hintContainer = this.getChildControl("hint-container");
      const caret = this.getChildControl("caret");

      caret.getContentElement().removeClass("hint-top");
      caret.getContentElement().removeClass("hint-right");
      caret.getContentElement().removeClass("hint-bottom");
      caret.getContentElement().removeClass("hint-left");
      switch (this.getOrientation()) {
        case this.self().orientation.TOP:
        case this.self().orientation.LEFT:
          caret.getContentElement().addClass(this.getOrientation() === this.self().orientation.LEFT ? "hint-left" : "hint-top");
          this._setLayout(this.getOrientation() === this.self().orientation.LEFT ? new qx.ui.layout.HBox() : new qx.ui.layout.VBox());
          this._add(hintContainer, {
            flex: 1
          });
          this._add(caret);
          break;
        case this.self().orientation.RIGHT:
        case this.self().orientation.BOTTOM:
          caret.getContentElement().addClass(this.getOrientation() === this.self().orientation.RIGHT ? "hint-right" : "hint-bottom");
          this._setLayout(this.getOrientation() === this.self().orientation.RIGHT ? new qx.ui.layout.HBox() : new qx.ui.layout.VBox());
          this._add(caret);
          this._add(hintContainer, {
            flex: 1
          });
          break;
      }
      switch (this.getOrientation()) {
        case this.self().orientation.RIGHT:
        case this.self().orientation.LEFT:
          caret.setHeight(0);
          caret.setWidth(5);
          break;
        case this.self().orientation.TOP:
        case this.self().orientation.BOTTOM:
          caret.setWidth(0);
          caret.setHeight(5);
          break;
      }
    },

    getLabel: function() {
      return this.getChildControl("label");
    },

    getText: function() {
      return this.getChildControl("label").getValue();
    },

    setText: function(text) {
      this.getChildControl("label").setValue(text);
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
          case this.self().orientation.TOP:
            properties.top = top - selfBounds.height;
            properties.left = Math.floor(left + (width - selfBounds.width) / 2);
            break;
          case this.self().orientation.RIGHT:
            properties.top = Math.floor(top + (height - selfBounds.height) / 2);
            properties.left = left + width;
            break;
          case this.self().orientation.BOTTOM:
            properties.top = top + height;
            properties.left = Math.floor(left + (width - selfBounds.width) / 2);
            break;
          case this.self().orientation.LEFT:
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

    _applyOrientation: function() {
      this._buildWidget();
      this.__updatePosition();
    },

    // overwritten
    getChildrenContainer: function() {
      return this.getChildControl("hint-container");
    },

    _applyElement: function(element, oldElement) {
      if (oldElement) {
        oldElement.removeListener("appear", this.__elementVisibilityHandler);
        oldElement.removeListener("disappear", this.__elementVisibilityHandler);
        this.__removeListeners(["move", "resize"]);
        this.__removeListeners(["scrollX", "scrollY"], true);
      }
      if (element) {
        const isElementVisible = qx.ui.core.queue.Visibility.isVisible(element);
        if (isElementVisible && this.isActive()) {
          this.show();
        }
        element.addListener("appear", this.__elementVisibilityHandler, this);
        element.addListener("disappear", this.__elementVisibilityHandler, this);
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
    },

    __attachEventHandlers: function() {
      this.addListener("appear", () => this.__updatePosition(), this);
    }
  }
});
