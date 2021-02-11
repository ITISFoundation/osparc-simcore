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
    fl.setColumnFlex(this._gridPos.label, 0);
    fl.setColumnAlign(this._gridPos.label, "left", "top");
    fl.setColumnFlex(this._gridPos.info, 0);
    fl.setColumnAlign(this._gridPos.info, "left", "middle");
    fl.setColumnFlex(this._gridPos.ctrlField, 1);
    fl.setColumnMinWidth(this._gridPos.ctrlField, 130);
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
      info: 1,
      ctrlField: 2
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

        const info = this._createInfoWHint(item.description);
        this._add(info, {
          row: this._row,
          column: this._gridPos.info
        });

        const field = this._createFieldWithMenu(item);
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
        this.__createNewParameter(field.key);
      }, this);
      menu.add(newParamBtn);

      const existingParamMenu = new qx.ui.menu.Menu();
      this.__populateExistingParamsMenu(field.key, existingParamMenu);
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getSweeper().addListener("changeParameters", () => {
        this.__populateExistingParamsMenu(field.key, existingParamMenu);
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

    __createNewParameter: function(fieldKey) {
      const title = this.tr("Create new parameter");
      const newParamName = new osparc.component.widget.Renamer(null, null, title);
      newParamName.addListener("labelChanged", e => {
        const study = osparc.store.Store.getInstance().getCurrentStudy();
        let newParameterLabel = e.getData()["newLabel"];
        newParameterLabel = newParameterLabel.replace(/ /g, "_");
        newParameterLabel = newParameterLabel.replace(/"/g, "'");
        if (study.getSweeper().parameterLabelExists(newParameterLabel)) {
          const msg = this.tr("Parameter name already exists");
          osparc.component.message.FlashMessenger.getInstance().logAs(msg, "ERROR");
        } else {
          const param = study.getSweeper().addNewParameter(newParameterLabel);
          this.addParameter(fieldKey, param);
          newParamName.close();
        }
      }, this);
      newParamName.center();
      newParamName.open();
    },

    __populateExistingParamsMenu: function(fieldKey, existingParamMenu) {
      existingParamMenu.removeAll();
      const study = osparc.store.Store.getInstance().getCurrentStudy();
      study.getSweeper().getParameters().forEach(param => {
        const paramButton = new qx.ui.menu.Button(param.label);
        paramButton.addListener("execute", () => {
          this.addParameter(fieldKey, param);
        }, this);
        existingParamMenu.add(paramButton);
      });
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

    hasAnyPortConnected: function() {
      const data = this._form.getData();
      for (const portId in data) {
        const ctrl = this._form.getControl(portId);
        if (ctrl && ctrl["link"]) {
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
      if (["Number", "Spinner"].includes(field.widgetType)) {
        const fieldWMenu = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
        fieldWMenu.add(field, {
          flex: 1
        });

        const menuBtn = this.__getMenuButton(field).set({
          visibility: "excluded"
        });
        osparc.data.model.Sweeper.isSweeperEnabled()
          .then(isSweeperEnabled => {
            menuBtn.setVisibility(isSweeperEnabled ? "visible" : "excluded");
          });
        fieldWMenu.add(menuBtn);
        return fieldWMenu;
      }
      return field;
    },

    _createInfoWHint: function(hint) {
      const infoWHint = new osparc.ui.hint.InfoHint(hint);
      return infoWHint;
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

    _getInfoFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.info);
    },

    _getCtrlFieldChild: function(portId) {
      return this._getLayoutChild(portId, this._gridPos.ctrlField);
    }
  }
});
