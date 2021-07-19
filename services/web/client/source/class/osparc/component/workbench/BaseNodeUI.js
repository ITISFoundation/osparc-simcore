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

qx.Class.define("osparc.component.workbench.BaseNodeUI", {
  extend: qx.ui.window.Window,
  include: osparc.component.filter.MFilterable,
  implement: osparc.component.filter.IFilterable,
  type: "abstract",

  construct: function() {
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
      contentPadding: 0
    });

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

  statics: {
    PORT_HEIGHT: 18,
    NODE_CONNECTED: "@FontAwesome5Regular/dot-circle/18",
    NODE_DISCONNECTED: "@FontAwesome5Regular/circle/18",

    captionHeight: function() {
      return osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().minHeight;
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

  members: {
    _inputOutputLayout: null,
    _inputLayout: null,
    _outputLayout: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "input-output":
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

    /**
      * @abstract
      */
    _createWindowLayout: function() {
      throw new Error("Abstract method called!");
    },

    getInputPort: function() {
      return this._inputLayout;
    },

    getOutputPort: function() {
      return this._outputLayout;
    },

    /**
      * @abstract
      */
    _createUIPorts: function() {
      throw new Error("Abstract method called!");
    },

    _createUIPortLabel: function(isInput) {
      const width = this.self().PORT_HEIGHT;
      const uiPort = new qx.ui.basic.Image().set({
        source: this.self().NODE_DISCONNECTED, // disconnected by default
        height: width,
        draggable: true,
        droppable: true,
        width: width,
        alignY: "middle",
        marginLeft: isInput ? -(parseInt(width/3)+1) : 0,
        marginRight: isInput ? 0 : -(parseInt(width/3)+1),
        backgroundColor: "background-main"
      });
      uiPort.setCursor("pointer");
      uiPort.getContentElement().setStyles({
        "border-radius": width+"px"
      });
      uiPort.isInput = isInput;
      return uiPort;
    },

    /**
      * @abstract
      */
    _createDragDropEventData: function(e, isInput) {
      throw new Error("Abstract method called!");
    },

    _addDragDropMechanism: function(uiPort, isInput) {
      [
        ["dragstart", "edgeDragStart"],
        ["dragover", "edgeDragOver"],
        ["drop", "edgeDrop"],
        ["dragend", "edgeDragEnd"]
      ].forEach(eventPair => {
        uiPort.addListener(eventPair[0], e => {
          const eData = this._createDragDropEventData(e, isInput);
          this.fireDataEvent(eventPair[1], eData);
        }, this);
      }, this);
    },

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = Math.max(this.getChildControl("captionbar").getSizeHint().height, this.self().captionHeight());
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width - 1;
      let y = bounds.top + captionHeight + this.self().PORT_HEIGHT/2;
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

    _setPositionFromEvent: function(e) {
      const sideBarWidth = this.__dragRange.left;
      const navigationBarHeight = this.__dragRange.top;
      const native = e.getNativeEvent();
      const x = native.clientX + this.__dragLeft - sideBarWidth;
      const y = native.clientY + this.__dragTop - navigationBarHeight;
      const coords = this.__scaleCoordinates(x, y);
      const insets = this.getLayoutParent().getInsets();
      this.setDomPosition(coords.x - (insets.left || 0), coords.y - (insets.top || 0));
      return coords;
    },

    // override qx.ui.core.MMovable
    _onMovePointerMove: function(e) {
      // Only react when dragging is active
      if (!this.hasState("move")) {
        return;
      }
      e.stopPropagation();
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

    /**
      * @abstract
      */
    _shouldApplyFilter: function(data) {
      throw new Error("Abstract method called!");
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
