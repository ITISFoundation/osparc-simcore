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
 * A special renderer for AutoForms which includes notes below the section header
 * widget and next to the individual form widgets.
 */


qx.Class.define("osparc.component.form.renderer.PropFormBase", {
  extend: qx.ui.form.renderer.Single,
  type: "abstract",

  /**
   * @param form {osparc.component.form.Auto} form widget to embedd
   * @param node {osparc.data.model.Node} Node owning the widget
   */
  construct: function(form, node) {
    if (node) {
      this.setNode(node);
    } else {
      this.setNode(null);
    }

    this.base(arguments, form);

    const fl = this._getLayout();
    fl.setColumnFlex(0, 0);
    fl.setColumnAlign(0, "left", "top");
    fl.setColumnFlex(1, 1);
    fl.setColumnMinWidth(1, 130);
  },

  properties: {
    node: {
      check: "osparc.data.model.Node",
      nullable: true
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _gridPos: {
      label: 0,
      ctrlField: 1
    },

    _visibility: {
      hidden: "Invisible",
      readOnly: "ReadOnly",
      readWrite: "ReadAndWrite"
    },

    addItems: function(items, names, title, itemOptions, headerOptions) {
      // add the header
      if (title !== null) {
        this._add(
          this._createHeader(title), {
            row: this._row,
            column: this._gridPos.label,
            colSpan: Object.keys(this._gridPos).length
          }
        );
        this._row++;
      }

      // add the items
      for (let i = 0; i < items.length; i++) {
        const item = items[i];

        const label = this._createLabel(names[i], item);
        label.setBuddy(item);
        this._add(label, {
          row: this._row,
          column: this._gridPos.label
        });

        const fieldWMenu = this._createFieldWithMenu(item);

        const field = this._createFieldWithHint(fieldWMenu, item.description);
        field.key = item.key;
        this._add(field, {
          row: this._row,
          column: this._gridPos.ctrlField
        });
        this._row++;
        this._connectVisibility(item, label);
        // store the names for translation
        if (qx.core.Environment.get("qx.dynlocale")) {
          this._names.push({
            name: names[i],
            label: label,
            item: items[i]
          });
        }
      }
    },

    getValues: function() {
      let data = this._form.getData();
      for (const portId in data) {
        let ctrl = this._form.getControl(portId);
        if (ctrl && ctrl["link"]) {
          data[portId] = ctrl["link"];
        }
        if (ctrl && ctrl["parameter"]) {
          data[portId] = "{{" + ctrl["parameter"].id + "}}";
        }
        // FIXME: "null" should be a valid input
        if (data[portId] === "null") {
          data[portId] = null;
        }
      }
      let filteredData = {};
      for (const key in data) {
        if (data[key] !== null) {
          filteredData[key] = data[key];
        }
      }
      return filteredData;
    },

    __getMenuButton: function(field) {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const newParamBtn = new qx.ui.menu.Button(this.tr("Set new parameter"));
      newParamBtn.addListener("execute", () => {
        const title = this.tr("Create new parameter");
        const subtitle = this.tr("Do not use whitespaces");
        const newParamName = new osparc.component.widget.Renamer(null, subtitle, title);
        newParamName.addListener("labelChanged", e => {
          const study = osparc.store.Store.getInstance().getCurrentStudy();
          const newLabel = e.getData()["newLabel"];
          if (study.parameterLabelExists(newLabel)) {
            const msg = this.tr("Parameter name already exists");
            osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
          } else {
            const param = study.addParameter(newLabel);
            this.addParameter(field.key, param);
            newParamName.close();
          }
        }, this);
        newParamName.center();
        newParamName.open();
      }, this);
      menu.add(newParamBtn);

      const existingParamMenu = new qx.ui.menu.Menu();
      const repopulateMenu = () => {
        existingParamMenu.removeAll();
        const study = osparc.store.Store.getInstance().getCurrentStudy();
        study.getParameters().forEach(param => {
          const paramButton = new qx.ui.menu.Button(param.label);
          paramButton.addListener("execute", () => {
            this.addParameter(field.key, param);
          }, this);
          existingParamMenu.add(paramButton);
        });
      };
      repopulateMenu();
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getSweeper().addListener("changeParameters", () => {
        repopulateMenu();
      }, this);

      const existingParamBtn = new qx.ui.menu.Button(this.tr("Set existing parameter"), null, null, existingParamMenu);
      menu.add(existingParamBtn);

      const menuBtn = new qx.ui.form.MenuButton().set({
        menu: menu,
        icon: "@FontAwesome5Solid/ellipsis-v/14",
        focusable: false
      });
      return menuBtn;
    },

    hasVisibleInputs: function() {
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.label && child.getBuddy().isVisible()) {
          return true;
        }
      }
      return false;
    },

    /**
      * @abstract
      */
    setAccessLevel: function() {
      throw new Error("Abstract method called!");
    },

    /**
      * @abstract
      */
    addParameter: function() {
      throw new Error("Abstract method called!");
    },

    _createFieldWithMenu: function(field) {
      const fieldWMenu = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      fieldWMenu.add(field, {
        flex: 1
      });

      const menuBtn = this.__getMenuButton(field);
      fieldWMenu.add(menuBtn);

      return fieldWMenu;
    },

    _createFieldWithHint: function(field, hint) {
      const fieldWHint = new osparc.component.form.FieldWHint(null, hint, field);
      return fieldWHint;
    },

    _getLayoutChild: function(portId, column) {
      let row = null;
      const children = this._getChildren();
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        const layoutProps = child.getLayoutProperties();
        if (layoutProps.column === this._gridPos.label &&
          child.getBuddy().key === portId) {
          row = layoutProps.row;
          break;
        }
      }
      if (row !== null) {
        for (let i=0; i<children.length; i++) {
          const child = children[i];
          const layoutProps = child.getLayoutProperties();
          if (layoutProps.column === column &&
            layoutProps.row === row) {
            return {
              child,
              idx: i
            };
          }
        }
      }
      return null;
    },

    _getLabelFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.label);
    },

    _getCtrlFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.ctrlField);
    }
  }
});
