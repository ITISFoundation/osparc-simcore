/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.ui.hint.Hint", {
  extend: qx.ui.core.Widget,

  construct: function(element, text) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.VBox());
    this.set({
      backgroundColor: "transparent"
    });

    this.__hintContainer = new qx.ui.container.Composite(new qx.ui.layout.Basic());
    this.__hintContainer.set({
      appearance: "hint"
    });

    this.__caret = new qx.ui.container.Composite().set({
      height: 5,
      backgroundColor: "transparent"
    });
    this.__caret.getContentElement().addClass("hint");
    this._add(this.__caret);
    this.__hintContainer.add(new qx.ui.basic.Label(text).set({
      rich: true,
      maxWidth: 250
    }));
    this._add(this.__hintContainer, {
      flex: 1
    });

    this.positionHint(element);
  },

  members: {
    positionHint: function(element) {
      this.addListener("appear", () => {
        const {
          top,
          left
        } = qx.bom.element.Location.get(element.getContentElement().getDomElement());
        const {
          width,
          height
        } = qx.bom.element.Dimension.getSize(element.getContentElement().getDomElement());
        const selfBounds = this.getBounds();
        this.setLayoutProperties({
          top: top + height,
          left: Math.floor(left + (width - selfBounds.width) / 2)
        });
      }, this);

      const root = qx.core.Init.getApplication().getRoot();
      root.add(this, {
        top: -10000
      });
    }
  }
});
