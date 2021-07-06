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

qx.Class.define("osparc.component.workbench.ParameterUI", {
  extend: qx.ui.window.Window,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,

  /**
   * @param parameter
   */
  construct: function(parameter) {
    this.base();

    const grid = new qx.ui.layout.Grid(3, 1);
    grid.setColumnFlex(0, 1);

    this.set({
      layout: grid,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      width: this.self().NODE_WIDTH,
      maxWidth: this.self().NODE_WIDTH,
      minWidth: this.self().NODE_WIDTH,
      contentPadding: 0
    });

    this.__parameter = parameter;

    this.__createWindowLayout();

    this.subscribeToFilterGroup("workbench");

    this.getChildControl("captionbar").setCursor("move");
    this.getChildControl("title").set({
      cursor: "move",
      textAlign: "center"
    });
  },

  properties: {
    scale: {
      check: "Number",
      event: "changeScale",
      nullable: false
    },

    appearance: {
      init: "window-small-cap",
      refine: true
    }
  },

  events: {
    "edgeDragStart": "qx.event.type.Data",
    "edgeDragOver": "qx.event.type.Data",
    "edgeDrop": "qx.event.type.Data",
    "edgeDragEnd": "qx.event.type.Data",
    "nodeMoving": "qx.event.type.Event",
    "nodeStoppedMoving": "qx.event.type.Event"
  },

  statics: {
    NODE_WIDTH: 100,
    NODE_HEIGHT: 80,
    PORT_HEIGHT: 16,
    CIRCLED_RADIUS: 32,
    captionHeight: function() {
      return osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().minHeight;
    }
  },

  members: {
    __parameter: null,
    __inputOutputLayout: null,
    __outputLayout: null,

    getNodeType: function() {
      return "parameter";
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "inputOutput":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          control.add(new qx.ui.core.Spacer(), {
            flex: 1
          });
          this.add(control, {
            row: 0,
            column: 0
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    getParameter: function() {
      return this.__parameter;
    },

    getParameterId: function() {
      if ("id" in this.__parameter) {
        return this.__parameter["id"];
      }
      return null;
    },

    __createWindowLayout: function() {
      this.__inputOutputLayout = this.getChildControl("inputOutput");
    },

    populateParameterLayout: function() {
      this.setCaption(this.__parameter["label"]);

      const isInput = false;
      this.__createUIPorts(isInput);

      const width = 80;
      this.__turnIntoCircledUI(width);
    },

    __turnIntoCircledUI: function(width) {
      this.set({
        width: width,
        maxWidth: width,
        minWidth: width
      });
      this.getContentElement().setStyles({
        "border-radius": this.self().CIRCLED_RADIUS+"px"
      });

      const value = this.__parameter["low"];
      const label = new qx.ui.basic.Label(String(value)).set({
        font: "text-24",
        allowGrowX: true,
        textAlign: "center",
        padding: 6
      });
      this.__inputOutputLayout.addAt(label, 1, {
        flex: 1
      });
    },

    getOutputPort: function() {
      return this.__outputLayout;
    },

    __createUIPorts: function() {
      const isInput = false;

      const portLabel = this.__createUIPortLabel(isInput);
      const label = {
        isInput: isInput,
        ui: portLabel
      };
      portLabel.setTextColor(osparc.utils.StatusUI.getColor("ready"));
      label.ui.isInput = false;
      this.__addDragDropMechanism(label.ui, isInput);

      this.__outputLayout = label;
      const nElements = this.__inputOutputLayout.getChildren().length;
      this.__inputOutputLayout.addAt(label.ui, nElements, {
        flex: 1
      });
    },

    __createUIPortLabel: function(isInput) {
      const labelText = isInput ? "in" : "out";
      const alignX = isInput ? "left" : "right";
      const uiPort = new qx.ui.basic.Label(labelText).set({
        height: this.self().PORT_HEIGHT,
        draggable: true,
        droppable: true,
        textAlign: alignX,
        allowGrowX: true,
        paddingLeft: 5,
        paddingRight: 5
      });
      uiPort.setCursor("pointer");
      return uiPort;
    },

    __addDragDropMechanism: function(uiPort, isInput) {
      [
        ["dragstart", "edgeDragStart"],
        ["dragover", "edgeDragOver"],
        ["drop", "edgeDrop"],
        ["dragend", "edgeDragEnd"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = {
            event: e,
            parameterId: this.__parameter["id"],
            isInput: isInput
          };
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = Math.max(this.getChildControl("captionbar").getSizeHint().height, this.self().captionHeight());
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width;
      let y = bounds.top + captionHeight + this.self().PORT_HEIGHT/2 + 1;
      return [x, y];
    },

    getCurrentBounds: function() {
      let bounds = this.getBounds();
      let cel = this.getContentElement();
      if (cel) {
        let domeEle = cel.getDomElement();
        if (domeEle) {
          bounds.left = parseInt(domeEle.style.left);
          bounds.top = parseInt(domeEle.style.top);
        }
      }
      return bounds;
    },

    __scaleCoordinates: function(x, y) {
      return {
        x: parseInt(x / this.getScale()),
        y: parseInt(y / this.getScale())
      };
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }
      const sideBarWidth = this.__dragRange.left;
      const navigationBarHeight = this.__dragRange.top;
      const native = e.getNativeEvent();
      const x = native.clientX + this.__dragLeft - sideBarWidth;
      const y = native.clientY + this.__dragTop - navigationBarHeight;
      const coords = this.__scaleCoordinates(x, y);
      const insets = this.getLayoutParent().getInsets();
      this.setDomPosition(coords.x - (insets.left || 0), coords.y - (insets.top || 0));
      e.stopPropagation();

      this.__parameter["xPos"] = coords.x;
      this.__parameter["yPos"] = coords.y;
      this.fireEvent("nodeMoving");
    },

    // override qx.ui.core.MMovable
    _onMovePointerUp : function(e) {
      if (this.hasListener("roll")) {
        this.removeListener("roll", this._onMoveRoll, this);
      }

      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }

      this._onMovePointerMove(e);

      this.fireEvent("nodeStoppedMoving");

      // Remove drag state
      this.removeState("move");

      this.releaseCapture();

      e.stopPropagation();
    },

    // implement osparc.component.filter.IFilterable
    _filter: function() {
      this.setOpacity(0.4);
    },

    // implement osparc.component.filter.IFilterable
    _unfilter: function() {
      this.setOpacity(1);
    },

    // implement osparc.component.filter.IFilterable
    _shouldApplyFilter: function(data) {
      if (data.text) {
        const label = this.__parameter["label"]
          .trim()
          .toLowerCase();
        if (label.indexOf(data.text) === -1) {
          return true;
        }
      }
      return false;
    },

    // implement osparc.component.filter.IFilterable
    _shouldReactToFilter: function(data) {
      if (data.text && data.text.length > 1) {
        return true;
      }
      if (data.tags && data.tags.length) {
        return true;
      }
      return false;
    }
  }
});
