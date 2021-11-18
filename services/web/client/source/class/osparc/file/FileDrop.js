/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.file.FileDrop", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());
    this.set({
      droppable: true
    });
    [
      "dragover", // on target (pointer over)
      "dragleave" // on target (pointer out)
    ].forEach(signalName => {
      this.addListener(signalName, e => {
        const dragging = signalName !== "dragleave";
        this.__dragging(e, dragging);
      }, this);
    });

    this.getContentElement().setStyles(this.self().getBorderStyle());

    this._createChildControlImpl("drop-here");
    this._createChildControlImpl("svg-layer");
  },

  statics: {
    getBorderStyle: function() {
      return {
        "border-radius": "20px",
        "border-color": qx.theme.manager.Color.getInstance().resolve("contrasted-background+"),
        "border-style": "dotted"
      };
    }
  },

  members: {
    __dropHint: null,

    _createChildControlImpl: function(id) {
      let control = null;
      switch (id) {
        case "drop-here":
          control = new qx.ui.basic.Label(this.tr("Drop here")).set({
            font: "title-14",
            alignX: "center",
            alignY: "middle"
          });
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "svg-layer":
          control = new osparc.component.workbench.SvgWidget();
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
      }
    },

    __getLeftOffset: function() {
      const leftOffset = window.innerWidth - this.getInnerSize().width;
      return leftOffset;
    },

    __getTopOffset: function() {
      const topOffset = window.innerHeight - this.getInnerSize().height;
      return topOffset;
    },

    __pointerEventToScreenPos: function(e) {
      return {
        x: e.getDocumentLeft() - this.__getLeftOffset(),
        y: e.getDocumentTop() - this.__getTopOffset()
      };
    },

    __dragging: function(e) {
      e.preventDefault();
      e.stopPropagation();

      let posX = 0;
      let posY = 0;
      if ("offsetX" in e && "offsetY" in e) {
        posX = e.offsetX + 2;
        posY = e.offsetY + 2;
      } else {
        const pos = this.__pointerEventToScreenPos(e);
        posX = pos.x;
        posY = pos.y;
      }

      if (this.__dropHint === null) {
        const dropHint = this.__dropHint = new qx.ui.basic.Label(this.tr("Drop me")).set({
          font: "title-14",
          textAlign: "center"
        });
        this._add(dropHint);
        const svgLayer = this.getChildControl("svg-layer");
        dropHint.rect = svgLayer.drawDashedRect(150, 80, posX, posY);
      }
      this.__dropHint.setLayoutProperties({
        left: posX,
        top: posY
      });
      osparc.component.workbench.SvgWidget.updateRect(this.__dropHint.rect, posX, posY);
    }
  }
});
