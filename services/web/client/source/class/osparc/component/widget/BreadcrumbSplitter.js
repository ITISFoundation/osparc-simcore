/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *
 */

qx.Class.define("osparc.component.widget.BreadcrumbSplitter", {
  extend: qx.ui.core.Widget,

  construct: function(w, h) {
    this.base(arguments);

    this.set({
      width: w,
      height: h
    });

    this.addListenerOnce("appear", () => {
      const randomID = Math.random().toString(36).substring(7);
      const el = this.getContentElement().getDomElement();
      qx.bom.element.Attribute.set(el, "id", randomID);
      const svgWrapper = new osparc.wrapper.Svg();
      svgWrapper.addListener("svgLibReady", () => {
        this.__canvas = svgWrapper.createEmptyCanvas(randomID);
        this.setReady(true);
        this.fireDataEvent("SvgWidgetReady", true);
        this.setShape("slash");
      });
      svgWrapper.init();
    });
  },

  properties: {
    ready: {
      check: "Boolean",
      init: false
    },

    shape: {
      check: ["slash", "arrow"],
      nullable: true,
      event: "changeShape",
      apply: "_applyShape"
    },

    leftWidget: {
      check: "qx.ui.core.Widget",
      nullable: true,
      apply: "_applyLeftWidget"
    },

    rightWidget: {
      check: "qx.ui.core.Widget",
      nullable: true,
      apply: "_applyRightWidget"
    }
  },

  events: {
    "SvgWidgetReady": "qx.event.type.Data"
  },

  statics: {
    getTriangleControlsLeft: function(w = 16, h = 32) {
      return [
        [0, 0],
        [h, 0],
        [0, w]
      ];
    },

    getTriangleControlsRight: function(w = 16, h = 32) {
      return [
        [h, 0],
        [0, w],
        [h, w]
      ];
    },

    getSlashControls: function(w = 16, h = 32) {
      return [
        [0, w],
        [h, 0]
      ];
    }
  },

  members: {
    __canvas: null,
    __leftPart: null,
    __rightPart: null,

    _applyShape: function(shape) {
      console.log(shape);
      switch (shape) {
        case "slash": {
          const controlsLeft = this.self().getTriangleControlsLeft(32, 16);
          this.__leftPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controlsLeft);
          break;
        }
      }
    },

    _applyLeftWidget: function(leftWidget) {
      if (this.__leftPart === null) {
        this.setShape("slash");
      }
      leftWidget.addListener("changeBackgroundColor", e => {
        const data = e.getData();
        osparc.wrapper.Svg.updatePolygonColor(this.__leftPart, data);
      }, this);
    },

    _applyRightWidget: function(rightWidget) {
      const controlsRight = this.self().getTriangleControlsRight(32, 16);
      this.__rightPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controlsRight);
      const controlsSlash = this.self().getSlashControls(32, 16);
      osparc.wrapper.Svg.drawLine(this.__canvas, controlsSlash);
    }
  }
});
