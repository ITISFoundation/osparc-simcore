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
      const el = this.getContentElement().getDomElement();
      const svgWrapper = osparc.wrapper.Svg.getInstance();
      svgWrapper.init()
        .then(() => {
          if (this.__canvas === null) {
            this.__canvas = svgWrapper.createEmptyCanvas(el);
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
      check: ["slash", "arrow", "separator", "plusBtn"],
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
    },

    getSeparatorControls: function(w = 16, h = 32) {
      return [w/2, 0, w/2, h];
    },

    getPlusBtnControlsLeft: function(w = 16, h = 32) {
      // return `M0 0 M0 0 L${w/2} 0 L${w/2} ${h/4} A${w/2} ${h/4} 0 1 0 ${w/2} ${h*3/4} L${w/2} ${h} L0 ${h} L0 0`;
      return `M0 0 M0 0 L8 0 L8 8 A8 8 0 1 0 8 24 L8 32 L0 32 L0 0`;
    },

    getPlusBtnControlsRight: function(w = 16, h = 32) {
      // return `M0 0 M${w/2} 0 L${w} 0 L${w} ${h} L0 ${h} L0 ${h*3/4} A${w/2} ${h/4} 0 1 0 0 ${h/4} L0 0`;
      return `M0 0 M8 0 L16 0 L16 32 L8 32 L8 24 A8 8 0 1 0 8 8 L8 0`;
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
        case "slash":
          controls = this.self().getTriangleControlsLeft(16, bounds.height);
          break;
        case "arrow":
          controls = this.self().getArrowControlsLeft(16, bounds.height);
          break;
        case "separator":
          controls = this.self().getSeparatorControls(16, bounds.height);
          break;
        case "plusBtn":
          controls = this.self().getPlusBtnControlsLeft(16, bounds.height);
          break;
      }
      if (controls) {
        switch (this.getShape()) {
          case "slash":
          case "arrow":
            this.__leftPart = osparc.wrapper.Svg.drawPolygon(this.__canvas, controls);
            break;
          case "separator":
            this.__leftPart = osparc.wrapper.Svg.drawLine(this.__canvas, controls)
              .move(16 / 2, 0);
            break;
          case "plusBtn":
            this.__leftPart = osparc.wrapper.Svg.drawPath(this.__canvas, controls);
            break;
        }

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
        case "slash":
          controls = this.self().getTriangleControlsRight(16, bounds.height);
          break;
        case "arrow":
          controls = this.self().getArrowControlsRight(16, bounds.height);
          break;
        case "separator":
          controls = this.self().getSeparatorControls(16, bounds.height);
          break;
        case "plusBtn":
          controls = this.self().getPlusBtnControlsRight(16, bounds.height);
          break;
      }
      if (controls) {
        switch (this.getShape()) {
          case "slash":
          case "arrow": {
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
            break;
          }
          case "separator":
            this.__rightPart = osparc.wrapper.Svg.drawLine(this.__canvas, controls)
              .move(16 / 2, 0);
            break;
          case "plusBtn":
            this.__rightPart = osparc.wrapper.Svg.drawPath(this.__canvas, controls);
            break;
        }
      }

      let polylineControls;
      let lineControls;
      switch (this.getShape()) {
        case "slash":
          polylineControls = this.self().getSlashControls(16, bounds.height);
          break;
        case "arrow":
          polylineControls = this.self().getArrowControls(16, bounds.height);
          break;
        case "sepatator":
          lineControls = this.self().getSeparatorControls(16, bounds.height);
          break;
      }
      if (polylineControls || lineControls) {
        let stroke = null;
        if (polylineControls) {
          stroke = osparc.wrapper.Svg.drawPolyline(this.__canvas, polylineControls);
        } else if (lineControls) {
          stroke = osparc.wrapper.Svg.drawLine(this.__canvas, lineControls);
        }
        const color = this.__getTextColor();
        osparc.wrapper.Svg.updateStrokeColor(stroke, color);
        rightWidget.addListener("changeDecorator", e => {
          const newColor = this.__getTextColor();
          osparc.wrapper.Svg.updateStrokeColor(stroke, newColor);
        }, this);
      }
    }
  }
});
