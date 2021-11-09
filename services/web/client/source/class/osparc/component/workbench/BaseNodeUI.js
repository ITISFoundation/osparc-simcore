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

    const grid = new qx.ui.layout.Grid(4, 1);
    grid.setColumnFlex(1, 1);

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

    this.getChildControl("captionbar").set({
      cursor: "move",
      paddingRight: 0,
      paddingLeft: this.self().PORT_WIDTH
    });

    const menuBtn = this.__getMenuButton();
    this.getChildControl("captionbar").add(menuBtn, {
      row: 0,
      column: 2
    });

    const captionTitle = this.getChildControl("title");
    captionTitle.set({
      rich: true,
      cursor: "move"
    });
    captionTitle.addListener("appear", () => {
      qx.event.Timer.once(() => {
        const labelDom = captionTitle.getContentElement().getDomElement();
        const maxWidth = parseInt(labelDom.style.width);
        // eslint-disable-next-line no-underscore-dangle
        const width = captionTitle.__contentSize.width;
        if (width > maxWidth) {
          captionTitle.setToolTipText(this.getNode().getLabel());
        }
      }, this, 50);
    });

    this.__nodeMoving = false;
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
    PORT_WIDTH: 11,
    NODE_CONNECTED: "@FontAwesome5Regular/dot-circle/18",
    NODE_DISCONNECTED: "@FontAwesome5Regular/circle/18",

    captionHeight: function() {
      return osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["window-small-cap/captionbar"].style().minHeight;
    }
  },

  events: {
    "renameNode": "qx.event.type.Data",
    "infoNode": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "edgeDragStart": "qx.event.type.Data",
    "edgeDragOver": "qx.event.type.Data",
    "edgeDrop": "qx.event.type.Data",
    "edgeDragEnd": "qx.event.type.Data",
    "nodeStartedMoving": "qx.event.type.Event",
    "nodeMoving": "qx.event.type.Event",
    "nodeStoppedMoving": "qx.event.type.Event"
  },

  members: {
    _inputLayout: null,
    _outputLayout: null,
    __nodeMoving: null,

    /**
      * @abstract
      */
    _createWindowLayout: function() {
      throw new Error("Abstract method called!");
    },

    __getMenuButton: function() {
      const optionsMenu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const renameBtn = new qx.ui.menu.Button().set({
        label: this.tr("Rename"),
        icon: "@FontAwesome5Solid/i-cursor/10"
      });
      renameBtn.addListener("execute", () => this.fireDataEvent("renameNode", this.getNodeId()));
      optionsMenu.add(renameBtn);

      const infoBtn = new qx.ui.menu.Button().set({
        label: this.tr("Information"),
        icon: "@FontAwesome5Solid/info/10"
      });
      infoBtn.addListener("execute", () => this.fireDataEvent("infoNode", this.getNodeId()));
      optionsMenu.add(infoBtn);

      const deleteBtn = new qx.ui.menu.Button().set({
        label: this.tr("Delete"),
        icon: "@FontAwesome5Solid/trash/10"
      });
      deleteBtn.addListener("execute", () => this.fireDataEvent("removeNode", this.getNodeId()));
      optionsMenu.add(deleteBtn);

      const menuBtn = new qx.ui.form.MenuButton().set({
        menu: optionsMenu,
        icon: "@FontAwesome5Solid/ellipsis-v/9",
        height: 18,
        width: 18,
        allowGrowX: false,
        allowGrowY: false
      });
      return menuBtn;
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
    _createPorts: function() {
      throw new Error("Abstract method called!");
    },

    _createPort: function(isInput, placeholder = false) {
      let port = null;
      const width = this.self().PORT_HEIGHT;
      const portMargin = this.self().PORT_HEIGHT - this.self().PORT_WIDTH;
      if (placeholder) {
        port = new qx.ui.core.Spacer(width, width);
      } else {
        port = new qx.ui.basic.Image().set({
          source: this.self().NODE_DISCONNECTED, // disconnected by default
          height: width,
          draggable: true,
          droppable: true,
          width: width,
          alignY: "top",
          backgroundColor: "background-main"
        });
        port.setCursor("pointer");
        port.getContentElement().setStyles({
          "border-radius": width+"px"
        });
        port.isInput = isInput;
      }
      port.set({
        marginLeft: isInput ? -portMargin : 0,
        marginRight: isInput ? 0 : -portMargin
      });

      this.add(port, {
        row: 0,
        column: isInput ? 0 : 2
      });

      if (isInput) {
        this._inputLayout = port;
      } else {
        this._outputLayout = port;
      }

      return port;
    },

    /**
      * @abstract
      */
    _createDragDropEventData: function(e, isInput) {
      throw new Error("Abstract method called!");
    },

    _addDragDropMechanism: function(port, isInput) {
      [
        ["dragstart", "edgeDragStart"],
        ["dragover", "edgeDragOver"],
        ["drop", "edgeDrop"],
        ["dragend", "edgeDragEnd"]
      ].forEach(eventPair => {
        port.addListener(eventPair[0], e => {
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
      if (this.__nodeMoving === false) {
        this.__nodeMoving = true;
        this.fireEvent("nodeStartedMoving");
      }
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

      this.__nodeMoving = false;
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
