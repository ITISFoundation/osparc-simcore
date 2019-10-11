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
    this._setLayout(new qx.ui.layout.VBox());
    this.set({
      backgroundColor: "transparent"
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
    root.add(this, {
      top: -10000
    });

    this.addListener("appear", () => this.updatePosition(), this);

    if (element) {
      this.setElement(element);
      if (text) {
        this.__hintContainer.setLayout(new qx.ui.layout.Basic());
        this.add(new qx.ui.basic.Label(text).set({
          rich: true,
          maxWidth: 250
        }));
      }
    }
  },

  properties: {
    element: {}
  },

  members: {
    updatePosition: function() {
      const {
        top,
        left
      } = qx.bom.element.Location.get(this.getElement().getContentElement().getDomElement());
      const {
        width,
        height
      } = qx.bom.element.Dimension.getSize(this.getElement().getContentElement().getDomElement());
      const selfBounds = this.getBounds();
      this.setLayoutProperties({
        top: top + height,
        left: Math.floor(left + (width - selfBounds.width) / 2)
      });
    },

    // overwritten
    getChildrenContainer: function() {
      return this.__hintContainer;
    }
  }
});
