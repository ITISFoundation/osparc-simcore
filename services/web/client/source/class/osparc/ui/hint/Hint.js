/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.hint.Hint", {
  extend: qx.ui.core.Widget,
  include: [qx.ui.core.MRemoteChildrenHandling, qx.ui.core.MRemoteLayoutHandling],

  construct: function(element, text) {
    this.base(arguments);
    this.__createWidget();

    if (element) {
      this.setElement(element);
    }

    // If it is a simple label
    if (text) {
      this.__hintContainer.setLayout(new qx.ui.layout.Basic());
      this.add(new qx.ui.basic.Label(text).set({
        rich: true,
        maxWidth: 250
      }));
    }
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
      apply: "_applyActive",
      nullable: false,
      init: true
    },
    orientation: {
      check: "String"
    }
  },

  members: {
    __hintContainer: null,
    __caret: null,

    __createWidget: function() {
      this._setLayout(new qx.ui.layout.VBox());
      this.set({
        backgroundColor: "transparent",
        visibility: "excluded"
      });

      this.__hintContainer = new qx.ui.container.Composite();
      this.__hintContainer.set({
        appearance: "hint"
      });

      this.__caret = new qx.ui.container.Composite().set({
        height: 5,
        backgroundColor: "transparent"
      });
      this.__caret.getContentElement().addClass("hint");
      this._add(this.__caret);
      this._add(this.__hintContainer, {
        flex: 1
      });

      const root = qx.core.Init.getApplication().getRoot();
      root.add(this);
    },

    __updatePosition: function() {
      const {
        top,
        left
      } = qx.bom.element.Location.get(this.getElement().getContentElement()
        .getDomElement());
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(this.getElement().getContentElement()
        .getDomElement());
      const selfBounds = this.getBounds() || this.getSizeHint();
      this.setLayoutProperties({
        top: top + height,
        left: Math.floor(left + (width - selfBounds.width) / 2)
      });
    },

    // overwritten
    getChildrenContainer: function() {
      return this.__hintContainer;
    },

    _applyElement: function(element, oldElement) {
      if (oldElement) {
        oldElement.removeListener("appear", this.__elementVisibilityHandler);
        oldElement.removeListener("disappear", this.__elementVisibilityHandler);
        oldElement.removeListener("move", this.__elementVisibilityHandler);
      }
      if (element) {
        const isElementVisible = qx.ui.core.queue.Visibility.isVisible(element);
        if (isElementVisible && this.isActive()) {
          this.show();
          this.__updatePosition();
        }
        element.addListener("appear", this.__elementVisibilityHandler, this);
        element.addListener("disappear", this.__elementVisibilityHandler, this);
        element.addListener("move", this.__elementVisibilityHandler, this);
      } else {
        this.exclude();
      }
    },

    __elementVisibilityHandler: function(e) {
      switch (e.getType()) {
        case "appear":
          this.show();
          this.__updatePosition();
          break;
        case "disappear":
          this.exclude();
          break;
        case "move":
          this.__updatePosition();
          break;
      }
    },

    __attachEventHandlers: function() {
      this.addListener("appear", () => this.__updatePosition(), this);
    }
  }
});
