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

/**
 *
 */

qx.Class.define("osparc.file.FolderViewer", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__reloadContent();
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    },

    mode: {
      check: ["list", "icons"],
      init: "list",
      nullable: false,
      event: "changeMode",
      apply: "__reloadContent"
    }
  },

  statics: {
    TPOS: {
      TYPE: 0,
      NAME: 1,
      DATE: 2,
      SIZE: 3,
      ID: 4
    }
  },

  members: {
    __currentFolder: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "header":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          this._add(control);
          break;
        case "folder-name": {
          const header = this.getChildControl("header");
          control = new qx.ui.basic.Label().set({
            allowGrowX: true
          });
          header.addAt(control, 0, {
            flex: 1
          });
          break;
        }
        case "view-options": {
          const header = this.getChildControl("header");
          control = new qx.ui.form.MenuButton(this.tr("View"));
          const menu = new qx.ui.menu.Menu();
          const listBtn = new qx.ui.menu.Button(this.tr("List"));
          listBtn.addListener("execute", () => {
            this.setMode("list");
          });
          menu.add(listBtn);
          const iconsBtn = new qx.ui.menu.Button(this.tr("Icons"));
          iconsBtn.addListener("execute", () => {
            this.setMode("icons");
          });
          menu.add(iconsBtn);
          control.setMenu(menu);
          header.addAt(control, 1);
          break;
        }
        case "table": {
          const tableModel = new qx.ui.table.model.Simple();
          tableModel.setColumns([
            this.tr("-"),
            this.tr("Name"),
            this.tr("Date Modified"),
            this.tr("Size"),
            this.tr("Id")
          ]);
          control = new osparc.ui.table.Table(tableModel, {
            // tableColumnModel: obj => new qx.ui.table.columnmodel.Resize(obj),
            initiallyHiddenColumns: [this.self().TPOS.ID]
          });
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "list" ? "visible" : "excluded"
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "icons-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow());
          this.bind("mode", control, "visibility", {
            converter: mode => mode === "icons" ? "visible" : "excluded"
          });
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    setFolder: function(folder) {
      this.__currentFolder = folder;
      this.__reloadContent();
    },

    __convertEntries: function(content) {
      const items = [];
      if (this.getMode() === "list") {
        content.forEach(entry => {
          const row = [];
          row.push(this.__getIcon(entry));
          row.push(entry.getLabel());
          row.push(entry.getLastModified ? entry.getLastModified() : "");
          row.push(entry.getSize ? entry.getSize() : "");
          row.push(entry.getItemId());
          items.push(row);
        });
      } else if (this.getMode() === "icons") {
        content.forEach(entry => {
          const btn = new qx.ui.form.ToggleButton(entry.getLabel()).set({
            icon: this.__getIcon(entry),
            toolTipText: entry.getLabel(),
            iconPosition: "top",
            selectable: true,
            width: 80,
            padding: 5
          });
          btn.itemId = entry.getItemId();
          items.push(btn);
        });
      }
      return items;
    },

    __getIcon: function(entry) {
      return this.__isFolder(entry) ? "@MaterialIcons/folder" : "@MaterialIcons/insert_drive_file";
    },

    __isFolder: function(entry) {
      if (entry.getIsDataset) {
        return entry.getIsDataset();
      }
      if (entry.getChildren) {
        return entry.getChildren().length;
      }
      return false;
    },

    __getEntries: function() {
      if (this.__currentFolder) {
        const children = this.__currentFolder.getChildren().toArray();
        return this.__convertEntries(children);
      }
      return [];
    },

    __reloadContent: function() {
      this.getChildControl("folder-name").set({
        value: this.__currentFolder ? this.__currentFolder.getLabel() : "Select folder"
      });
      this.getChildControl("view-options");

      const entries = this.__getEntries();
      if (this.getMode() === "list") {
        const table = this.getChildControl("table");
        table.getTableColumnModel().setDataCellRenderer(this.self().TPOS.TYPE, new qx.ui.table.cellrenderer.Image());
        table.setColumnWidth(this.self().TPOS.TYPE, 20);
        table.setData(entries);
      } else if (this.getMode() === "icons") {
        const iconsLayout = this.getChildControl("icons-layout");
        iconsLayout.removeAll();
        const iconsGroup = new qx.ui.form.RadioGroup();
        entries.forEach(entry => {
          iconsGroup.add(entry);
          iconsLayout.add(entry);
        });
      }
    }
  }
});
