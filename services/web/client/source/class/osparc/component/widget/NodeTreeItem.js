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
 *     createItem: () => new osparc.component.widget.NodeTreeItem(),
 *     bindItem: (c, item, id) => {
 *       c.bindDefaultProperties(item, id);
 *       c.bindProperty("label", "label", null, item, id);
 *       c.bindProperty("nodeId", "nodeId", null, item, id);
 *     }
 *   });
 * </pre>
 */

qx.Class.define("osparc.component.widget.NodeTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  construct: function() {
    this.base(arguments);

    this.set({
      indent: 8,
      alignY: "middle"
    });

    this.getContentElement().setStyles({
      "border-radius": "6px"
    });
    this.__setNotHoveredStyle();
    this.__attachEventHandlers();
  },

  properties: {
    nodeId : {
      check : "String",
      event: "changeNodeId",
      apply: "__applyNodeId",
      nullable : true
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

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "buttons": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(0).set({
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
          control.addListener("execute", () => this.fireDataEvent("fullscreenNode", this.getNodeId()));
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
        case "options-rename-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Rename"),
            icon: "@FontAwesome5Solid/i-cursor/10"
          });
          control.addListener("execute", () => this.fireDataEvent("renameNode", this.getNodeId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "options-info-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Information"),
            icon: "@FontAwesome5Solid/info/10"
          });
          control.addListener("execute", () => this.fireDataEvent("infoNode", this.getNodeId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "options-delete-button": {
          control = new qx.ui.menu.Button().set({
            label: this.tr("Delete"),
            icon: "@FontAwesome5Solid/trash/10"
          });
          control.addListener("execute", () => this.fireDataEvent("deleteNode", this.getNodeId()));
          const optionsMenu = this.getChildControl("options-menu-button");
          optionsMenu.getMenu().add(control);
          break;
        }
        case "node-id": {
          control = new qx.ui.basic.Label().set({
            maxWidth: 70
          });
          this.bind("nodeId", control, "value", {
            converter: value => value && value.substring(0, 8)
          });
          const permissions = osparc.data.Permissions.getInstance();
          permissions.bind("role", control, "visibility", {
            converter: () => permissions.canDo("study.nodestree.uuid.read") ? "visible" : "excluded"
          });
          this.addWidget(control);
        }
      }

      return control || this.base(arguments, id);
    },

    _addWidgets: function() {
      // Here's our indentation and tree-lines
      this.addSpacer();
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
      label.set({
        allowGrowX: true,
        allowShrinkX: true
      });
      label.setLayoutProperties({
        flex: 1
      });

      this.getChildControl("fullscreen-button");
      this.getChildControl("options-rename-button");
      this.getChildControl("options-info-button");
      this.getChildControl("options-delete-button");
      this.getChildControl("node-id");
    },

    __applyNodeId: function(nodeId) {
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      osparc.utils.Utils.setIdToWidget(this, "nodeTreeItem");
      if (nodeId === study.getUuid()) {
        osparc.utils.Utils.setMoreToWidget(this, "root");
      } else {
        osparc.utils.Utils.setMoreToWidget(this, nodeId);
      }
    },

    __attachEventHandlers: function() {
      this.addListener("mouseover", () => {
        this.getChildControl("buttons").show();
        this.__setHoveredStyle();
      });
      this.addListener("mouseout", () => {
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
      this.getContentElement().setStyles({
        "border": "1px solid " + qx.theme.manager.Color.getInstance().resolve("background-selected")
      });
    },

    __setNotHoveredStyle: function() {
      this.getContentElement().setStyles({
        "border": "1px solid transparent"
      });
    }
  }
});
