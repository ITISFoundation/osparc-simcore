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

qx.Class.define("osparc.workbench.BaseNodeUI", {
  extend: qx.ui.window.Window,
  include: osparc.filter.MFilterable,
  implement: osparc.filter.IFilterable,
  type: "abstract",

  construct: function() {
    this.base();

    const grid = new qx.ui.layout.Grid(4, 1);
    grid.setColumnFlex(1, 1);

    this.set({
      appearance: "node-ui-cap",
      layout: grid,
      showMinimize: false,
      showMaximize: false,
      showClose: false,
      showStatusbar: false,
      resizable: false,
      allowMaximize: false,
      contentPadding: this.self().CONTENT_PADDING
    });

    this.getContentElement().setStyles({
      "border-radius": "4px"
    });

    this.subscribeToFilterGroup("workbench");

    const captionBar = this.getChildControl("captionbar");
    captionBar.set({
      cursor: "move",
      paddingRight: 0,
      paddingLeft: this.self().PORT_WIDTH
    });

    const menuBtn = this.__getMenuButton();
    captionBar.add(menuBtn, {
      row: 0,
      column: this.self().CAPTION_POS.MENU
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
          this.getNode().bind("label", captionTitle, "toolTipText");
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

    isMovable: {
      check: "Boolean",
      init: true,
      nullable: false
    }
  },

  statics: {
    PORT_HEIGHT: 18,
    PORT_WIDTH: 11,
    CONTENT_PADDING: 2,
    PORT_CONNECTED: "@FontAwesome5Regular/dot-circle/18",
    PORT_DISCONNECTED: "@FontAwesome5Regular/circle/18",

    CAPTION_POS: {
      ICON: 0, // from qooxdoo
      TITLE: 1, // from qooxdoo
      LOCK: 2,
      MARKER: 3,
      DEPRECATED: 4,
      MENU: 5
    },

    captionHeight: function() {
      return osparc.theme.Appearance.appearances["node-ui-cap/captionbar"].style().height ||
        osparc.theme.Appearance.appearances["node-ui-cap/captionbar"].style().minHeight;
    }
  },

  events: {
    "renameNode": "qx.event.type.Data",
    "infoNode": "qx.event.type.Data",
    "markerClicked": "qx.event.type.Data",
    "removeNode": "qx.event.type.Data",
    "edgeDragStart": "qx.event.type.Data",
    "edgeDragOver": "qx.event.type.Data",
    "edgeDrop": "qx.event.type.Data",
    "edgeDragEnd": "qx.event.type.Data",
    "nodeMovingStart": "qx.event.type.Event",
    "nodeMoving": "qx.event.type.Event",
    "nodeMovingStop": "qx.event.type.Event"
  },

  members: {
    __inputLayout: null,
    __outputLayout: null,
    _optionsMenu: null,
    _markerBtn: null,
    _deleteBtn: null,
    __nodeMoving: null,

    __getMenuButton: function() {
      const optionsMenu = this._optionsMenu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const renameBtn = new qx.ui.menu.Button().set({
        label: this.tr("Rename"),
        icon: "@FontAwesome5Solid/i-cursor/10"
      });
      renameBtn.getChildControl("shortcut").setValue("F2");
      renameBtn.addListener("execute", () => this.fireDataEvent("renameNode", this.getNodeId()));
      optionsMenu.add(renameBtn);

      const markerBtn = this._markerBtn = new qx.ui.menu.Button().set({
        icon: "@FontAwesome5Solid/bookmark/10",
        visibility: "excluded"
      });
      optionsMenu.add(markerBtn);

      const infoBtn = new qx.ui.menu.Button().set({
        label: this.tr("Information..."),
        icon: "@FontAwesome5Solid/info/10"
      });
      infoBtn.getChildControl("shortcut").setValue("I");
      infoBtn.addListener("execute", () => this.fireDataEvent("infoNode", this.getNodeId()));
      optionsMenu.add(infoBtn);

      const deleteBtn = this._deleteBtn = new qx.ui.menu.Button().set({
        label: this.tr("Delete"),
        icon: "@FontAwesome5Solid/trash/10"
      });
      deleteBtn.getChildControl("shortcut").setValue("Del");
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
      return this.__inputLayout;
    },

    getOutputPort: function() {
      return this.__outputLayout;
    },

    _createPort: function(isInput, placeholder = false) {
      let port = null;
      const width = this.self().PORT_HEIGHT;
      if (placeholder) {
        port = new qx.ui.core.Spacer(width, width);
      } else {
        port = new qx.ui.basic.Image().set({
          source: this.self().PORT_DISCONNECTED, // disconnected by default
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
      // make the ports exit the NodeUI
      port.set({
        marginLeft: isInput ? (-10 + this.self().CONTENT_PADDING) : 0,
        marginRight: isInput ? 0 : (-10 - this.self().CONTENT_PADDING)
      });

      this.add(port, {
        row: 0,
        column: isInput ? 0 : 2
      });

      if (isInput) {
        this.__inputLayout = port;
      } else {
        this.__outputLayout = port;
      }

      return port;
    },

    getEdgePoint: function(port) {
      const bounds = this.getCurrentBounds();
      const captionHeight = Math.max(this.getChildControl("captionbar").getSizeHint().height, this.self().captionHeight());
      const x = port.isInput ? bounds.left - 6 : bounds.left + bounds.width - 1;
      const y = bounds.top + captionHeight + this.self().PORT_HEIGHT/2 + 2;
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
      if (!this.hasState("move") || !this.getIsMovable()) {
        return;
      }
      e.stopPropagation();
      if (this.__nodeMoving === false) {
        this.__nodeMoving = true;
        this.fireEvent("nodeMovingStart");
      }
      this.fireEvent("nodeMoving");
    },

    // override qx.ui.core.MMovable
    _onMovePointerUp : function(e) {
      if (this.hasListener("roll")) {
        this.removeListener("roll", this._onMoveRoll, this);
      }

      // Only react when dragging is active
      if (!this.hasState("move") || !this.getIsMovable()) {
        return;
      }

      this._onMovePointerMove(e);

      this.__nodeMoving = false;
      this.fireEvent("nodeMovingStop");

      // Remove drag state
      this.removeState("move");

      this.releaseCapture();

      e.stopPropagation();
    },

    // implement osparc.filter.IFilterable
    _filter: function() {
      this.setOpacity(0.4);
    },

    // implement osparc.filter.IFilterable
    _unfilter: function() {
      this.setOpacity(1);
    },

    /**
      * @abstract
      */
    _shouldApplyFilter: function(data) {
      throw new Error("Abstract method called!");
    },

    // implement osparc.filter.IFilterable
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
