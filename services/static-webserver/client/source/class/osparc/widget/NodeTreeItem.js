/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * VirtualTreeItem used mainly by NodesTree
 *
 *   It consists of an entry icon, label and Node id
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   tree.setDelegate({
 *     createItem: () => new osparc.widget.NodeTreeItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("label", "label", null, item, id);
 *       c.bindProperty("nodeId", "nodeId", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("osparc.widget.NodeTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);

    this.set({
      indent: 5,
      textColor: "text",
      allowGrowX: true,
      alignY: "middle",
      decorator: "rounded",
    });

    this.__setNotHoveredStyle();
    this.__attachEventHandlers();
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false,
      apply: "__applyStudy",
      event: "changeStudy"
    },

    node: {
      check: "osparc.data.model.Node",
      init: null,
      nullable: false,
      apply: "__applyNode",
      event: "changeNode"
    },

    id: {
      check: "String",
      init: null,
      nullable: false,
      event: "changeId"
    },

    iconColor: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeIconColor",
      apply: "__applyIconColor"
    },

    simpleNode: {
      check: "Boolean",
      nullable: true,
      init: false,
      event: "changeSimpleNode"
    }
  },

  events: {
    "fullscreenNode": "qx.event.type.Data",
    "renameNode": "qx.event.type.Data",
    "infoNode": "qx.event.type.Data",
    "deleteNode": "qx.event.type.Data"
  },

  members: {
    __optionsMenu: null,

    __applyStudy: function(study) {
      const label = this.getChildControl("label");
      osparc.utils.Utils.setKeyToWidget(label, "root");

      study.bind("name", this, "toolTipText");

      this.getChildControl("delete-button").exclude();
    },

    __applyNode: function(node) {
      const label = this.getChildControl("label");
      osparc.utils.Utils.setKeyToWidget(label, node.getNodeId());

      node.bind("label", this, "toolTipText");

      if (node.isDynamic()) {
        this.getChildControl("fullscreen-button").show();

        const startButton = this.getChildControl("start-button");
        node.attachHandlersToStartButton(startButton);

        const stopButton = this.getChildControl("stop-button");
        node.attachHandlersToStopButton(stopButton);
      }

      const markerBtn = this.getChildControl("marker-button");
      markerBtn.show();
      node.bind("marker", markerBtn, "label", {
        converter: val => val ? this.tr("Remove Marker") : this.tr("Add Marker")
      });

      const marker = this.getChildControl("marker");
      const updateMarker = () => {
        node.bind("marker", marker, "visibility", {
          converter: val => val ? "visible" : "excluded"
        });
        if (node.getMarker()) {
          node.getMarker().bind("color", marker, "textColor");
        }
      };
      node.addListener("changeMarker", () => updateMarker());
      updateMarker();

      const deleteBtn = this.getChildControl("delete-button");
      node.getStudy().bind("pipelineRunning", deleteBtn, "enabled", {
        converter: running => !running
      });
    },

    __applyIconColor: function(textColor) {
      this.getChildControl("icon").set({
        textColor
      });
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "buttons": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          control.exclude();
          this.addWidget(control);
          break;
        }
        case "fullscreen-button": {
          control = new qx.ui.form.Button().set({
            icon: "@MaterialIcons/fullscreen/12",
            backgroundColor: "transparent",
            toolTipText: this.tr("Full Screen"),
            alignY: "middle",
            visibility: "excluded"
          });
          control.addListener("execute", () => this.fireDataEvent("fullscreenNode", this.getId()));
          const part = this.getChildControl("buttons");
          part.add(control);
          break;
        }
        case "options-menu-button": {
          const optionsMenu = this.__optionsMenu = new qx.ui.menu.Menu().set({
            position: "bottom-right"
          });
          control = new qx.ui.form.MenuButton().set({
            menu: optionsMenu,
            icon: "@FontAwesome5Solid/ellipsis-v/8",
            allowGrowX: false,
            alignY: "middle"
          });
          const part = this.getChildControl("buttons");
          part.add(control);
          break;
        }
        case "start-button": {
          control = new qx.ui.menu.Button().set({
            backgroundColor: "background-main",
            label: this.tr("Start"),
            icon: "@FontAwesome5Solid/play/10",
            visibility: "excluded"
          });
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "stop-button": {
          control = new qx.ui.menu.Button().set({
            backgroundColor: "background-main",
            label: this.tr("Stop"),
            icon: "@FontAwesome5Solid/stop/10",
            visibility: "excluded"
          });
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "rename-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Rename"),
            icon: "@FontAwesome5Solid/i-cursor/10"
          });
          control.getChildControl("shortcut").setValue("F2");
          control.addListener("execute", () => this.fireDataEvent("renameNode", this.getId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "marker-button": {
          control = new qx.ui.menu.Button().set({
            icon: "@FontAwesome5Solid/bookmark/10",
            visibility: "excluded"
          });
          control.addListener("execute", () => this.getNode().toggleMarker());
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "info-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Information..."),
            icon: "@FontAwesome5Solid/info/10"
          });
          control.getChildControl("shortcut").setValue("I");
          control.addListener("execute", () => this.fireDataEvent("infoNode", this.getId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "delete-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Delete"),
            icon: "@FontAwesome5Solid/trash/10"
          });
          control.getChildControl("shortcut").setValue("Del");
          control.addListener("execute", () => this.fireDataEvent("deleteNode", this.getId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "node-id": {
          control = new qx.ui.basic.Label().set({
            maxWidth: 70,
            alignY: "middle",
            cursor: "copy"
          });
          control.addListener("tap", () => osparc.utils.Utils.copyTextToClipboard(this.getId()));
          this.bind("id", control, "value", {
            converter: value => value && value.substring(0, 8)
          });
          const permissions = osparc.data.Permissions.getInstance();
          permissions.bind("role", control, "visibility", {
            converter: () => !this.isSimpleNode() && permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded"
          });
          this.bind("simpleNode", control, "visibility", {
            converter: simpleNode => !simpleNode && permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded"
          });
          this.addWidget(control);
          break;
        }
        case "marker":
          control = new qx.ui.basic.Image().set({
            source: "@FontAwesome5Solid/bookmark/12",
            padding: 4,
            visibility: "excluded"
          });
          this.addWidget(control);
          break;
      }

      return control || this.base(arguments, id);
    },

    _addWidgets: function() {
      // Here's our indentation and tree-lines
      this.addOpenButton();

      // The standard tree icon follows
      this.addIcon();
      this.getChildControl("icon").set({
        alignX: "center",
        alignY: "middle",
        width: 22
      });

      // The label
      this.addLabel();
      const label = this.getChildControl("label");
      osparc.utils.Utils.setIdToWidget(label, "nodeTreeItem");
      label.set({
        allowGrowX: true,
        allowShrinkX: true,
        // override the one set in osparc-theme
        paddingTop: 0
      });
      label.setLayoutProperties({
        flex: 1
      });

      this.getChildControl("fullscreen-button");
      this.getChildControl("start-button");
      this.getChildControl("stop-button");
      this.getChildControl("rename-button");
      this.getChildControl("marker-button");
      this.getChildControl("info-button");
      this.getChildControl("delete-button");
      this.getChildControl("node-id");
      this.getChildControl("marker");
    },

    __attachEventHandlers: function() {
      this.addListener("mouseover", () => {
        if (this.isSimpleNode()) {
          return;
        }
        this.getChildControl("buttons").show();
        this.__setHoveredStyle();
      });
      this.addListener("mouseout", () => {
        if (this.isSimpleNode()) {
          return;
        }
        if (this.__optionsMenu.isVisible()) {
          const hideButtonsIfMouseOut = event => {
            if (osparc.utils.Utils.isMouseOnElement(this.__optionsMenu, event, 5)) {
              return;
            }
            document.removeEventListener("mousemove", hideButtonsIfMouseOut);
            this.getChildControl("buttons").exclude();
            this.__optionsMenu.exclude();
          };
          document.addEventListener("mousemove", hideButtonsIfMouseOut);
        } else {
          this.getChildControl("buttons").exclude();
        }
        this.__setNotHoveredStyle();
      });
    },

    __setHoveredStyle: function() {
      osparc.utils.Utils.addBorder(this, 1, qx.theme.manager.Color.getInstance().resolve("background-selected-dark"));
    },

    __setNotHoveredStyle: function() {
      osparc.utils.Utils.hideBorder(this);
    }
  }
});
