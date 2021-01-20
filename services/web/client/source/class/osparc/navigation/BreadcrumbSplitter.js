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

qx.Class.define("osparc.navigation.BreadcrumbSplitter", {
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
      const svgWrapper = osparc.wrapper.Svg.getInstance();
      svgWrapper.init()
        .then(() => {
          if (this.__canvas === null) {
            this.__canvas = svgWrapper.createEmptyCanvas(randomID);
            this.setReady(true);
            this.fireDataEvent("SvgWidgetReady", true);
          }
        }, this);
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
      const offsetH = 4;
      const offsetW = Math.round(offsetH*w/h);
      return [
        [w-offsetW, offsetH],
        [offsetW, h-offsetH]
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

    __getTextColor: function() {
      return qx.theme.manager.Color.getInstance().resolve("text");
    },

    __getBGColor: function(decoratorName) {
      const decorator = qx.theme.manager.Decoration.getInstance().resolve(decoratorName);
      if (decorator) {
        const decoratorBG = decorator.getBackgroundColor();
        return qx.theme.manager.Color.getInstance().resolve(decoratorBG);
      }
      return null;
    },

    _applyLeftWidget: function(leftWidget) {
      const bounds = leftWidget.getBounds();
      this.set({
        zIndex: leftWidget.getZIndex()+1,
        marginTop: bounds.top
      });

      let controls;
      switch (this.getShape()) {
        case "slash": {
          controls = this.self().getTriangleControlsLeft(16, bounds.height);
          break;
        }
        case "arrow": {
          controls = this.self().getArrowControlsLeft(16, bounds.height);
          break;
        }
      }
      if (controls) {
        this.__leftPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controls);
        const color = this.__getBGColor(leftWidget.getDecorator());
        if (color) {
          osparc.wrapper.Svg.updatePolygonColor(this.__leftPart, color);
        }
        leftWidget.addListener("changeDecorator", e => {
          const newColor = this.__getBGColor(leftWidget.getDecorator());
          if (newColor) {
            osparc.wrapper.Svg.updatePolygonColor(this.__leftPart, newColor);
          }
        }, this);
      }
    },

    _applyRightWidget: function(rightWidget) {
      const bounds = rightWidget.getBounds();
      this.set({
        zIndex: rightWidget.getZIndex()+1,
        marginTop: bounds.top
      });

      let controls;
      switch (this.getShape()) {
        case "slash": {
          controls = this.self().getTriangleControlsRight(16, bounds.height);
          break;
        }
        case "arrow": {
          controls = this.self().getArrowControlsRight(16, bounds.height);
          break;
        }
      }
      if (controls) {
        this.__rightPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controls);
        const color = this.__getBGColor(rightWidget.getDecorator());
        if (color) {
          osparc.wrapper.Svg.updatePolygonColor(this.__rightPart, color);
        }
        rightWidget.addListener("changeDecorator", e => {
          const newColor = this.__getBGColor(rightWidget.getDecorator());
          if (newColor) {
            osparc.wrapper.Svg.updatePolygonColor(this.__rightPart, newColor);
          }
        }, this);
      }

      let plControls;
      switch (this.getShape()) {
        case "slash": {
          plControls = this.self().getSlashControls(16, bounds.height);
          break;
        }
        case "arrow": {
          plControls = this.self().getArrowControls(16, bounds.height);
          break;
        }
      }
      if (plControls) {
        const polyline = osparc.wrapper.Svg.drawPolyline(this.__canvas, plControls);
        const color = this.__getTextColor();
        osparc.wrapper.Svg.updatePolylineColor(polyline, color);
        rightWidget.addListener("changeDecorator", e => {
          const newColor = this.__getTextColor();
          osparc.wrapper.Svg.updatePolylineColor(polyline, newColor);
        }, this);
      }
    }
  }
});
