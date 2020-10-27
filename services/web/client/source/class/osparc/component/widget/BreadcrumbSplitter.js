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
      init: "slash"
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
        [0, h],
        [w, 0]
      ];
    },

    getTriangleControlsRight: function(w = 16, h = 32) {
      return [
        [0, h],
        [w, 0],
        [w, h]
      ];
    },

    getSlashControls: function(w = 16, h = 32) {
      const offset = 4;
      return [
        [w-offset, offset],
        [offset, h-offset]
      ];
    },

    getArrowControlsLeft: function(w = 16, h = 32) {
      return [
        [0, 0],
        [w, h/2],
        [0, h]
      ];
    },

    getArrowControlsRight: function(w = 16, h = 32) {
      return [
        [w, 0],
        [0, 0],
        [w, h/2],
        [0, h],
        [w, h]
      ];
    },

    getArrowControls: function(w = 16, h = 32) {
      return [
        [0, 0],
        [w, h/2],
        [0, h]
      ];
    }
  },

  members: {
    __canvas: null,
    __leftPart: null,
    __rightPart: null,

    __getBGColor: function(decoratorName) {
      const decorator = qx.theme.manager.Decoration.getInstance().resolve(decoratorName);
      const decoratorBG = decorator.getBackgroundColor();
      return qx.theme.manager.Color.getInstance().resolve(decoratorBG);
    },

    _applyLeftWidget: function(leftWidget) {
      this.setZIndex(leftWidget.getZIndex()+1);
      let controls;
      switch (this.getShape()) {
        case "slash": {
          controls = this.self().getTriangleControlsLeft(16, 32);
          break;
        }
        case "arrow": {
          controls = this.self().getArrowControlsLeft(16, 32);
          break;
        }
      }
      if (controls) {
        this.__leftPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controls);
        const color = this.__getBGColor(leftWidget.getDecorator());
        osparc.wrapper.Svg.updatePolygonColor(this.__leftPart, color);
        leftWidget.addListener("changeDecorator", e => {
          const newColor = this.__getBGColor(leftWidget.getDecorator());
          osparc.wrapper.Svg.updatePolygonColor(this.__leftPart, newColor);
        }, this);
      }
    },

    _applyRightWidget: function(rightWidget) {
      this.setZIndex(rightWidget.getZIndex()+1);
      let controls;
      switch (this.getShape()) {
        case "slash": {
          controls = this.self().getTriangleControlsRight(16, 32);
          break;
        }
        case "arrow": {
          controls = this.self().getArrowControlsRight(16, 32);
          break;
        }
      }
      if (controls) {
        this.__rightPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controls);
        const color = this.__getBGColor(rightWidget.getDecorator());
        osparc.wrapper.Svg.updatePolygonColor(this.__rightPart, color);
        rightWidget.addListener("changeDecorator", e => {
          const newColor = this.__getBGColor(rightWidget.getDecorator());
          osparc.wrapper.Svg.updatePolygonColor(this.__rightPart, newColor);
        }, this);
      }

      switch (this.getShape()) {
        case "slash": {
          const controlsSlash = this.self().getSlashControls(16, 32);
          osparc.wrapper.Svg.drawLine(this.__canvas, controlsSlash);
          break;
        }
        case "arrow": {
          const controlsArrow = this.self().getArrowControls(16, 32);
          osparc.wrapper.Svg.drawLine(this.__canvas, controlsArrow);
          break;
        }
      }
    }
  }
});
