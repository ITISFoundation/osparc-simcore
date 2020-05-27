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
 * View that shows who you want to share the resource with:
 * - Everyone
 * - My organizations
 * - Private
 */

qx.Class.define("osparc.component.export.ShareWith", {
  extend: qx.ui.groupbox.GroupBox,

  construct: function(header, filterGroupId) {
    this.base(arguments, header);

    this.set({
      appearance: "settings-groupbox",
      layout: new qx.ui.layout.VBox(10)
    });

    const store = osparc.store.Store.getInstance();
    Promise.all([
      store.getGroupsMe(),
      store.getGroupsAll()
    ])
      .then(values => {
        const groupMe = values[0];
        const groupAll = values[1];
        this.__sharingOptions["me"]["gid"] = groupMe["gid"];
        this.__sharingOptions["all"]["gid"] = groupAll["gid"];
        this.__buildLayout(filterGroupId);
      });
  },

  properties: {
    ready: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeReady"
    }
  },

  members: { // eslint-disable-line qx-rules/no-refs-in-members
    __sharingOptions: {
      "me": {
        shareContextId: 0,
        label: "Private",
        gid: null
      },
      "orgs": {
        shareContextId: 1,
        label: "Organizations",
        gid: null
      },
      "all": {
        shareContextId: 2,
        label: "Everyone",
        gid: null
      }
    },
    __rbManager: null,
    __myOrganizationsHB: null,

    __buildLayout: function(filterGroupId) {
      this.__rbManager = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });

      for (let [sharingOptionKey, sharingOption] of Object.entries(this.__sharingOptions)) {
        const rb = new qx.ui.form.RadioButton(sharingOption.label);
        rb.shareContextId = sharingOption.shareContextId;
        if (sharingOptionKey === "orgs") {
          const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
          const myOrganizationsHB = this.__myOrganizationsHB = new osparc.component.filter.Organizations(filterGroupId);
          vBox.add(rb);
          vBox.add(myOrganizationsHB);
          this.add(vBox);
        } else {
          rb.gid = sharingOption["gid"];
          this.add(rb);
        }
        this.__rbManager.add(rb);
      }

      this.__rbManager.addListener("changeSelection", this.__onChangeSelection, this);
      this.__rbManager.setSelection([]);
    },

    __onChangeSelection: function() {
      const selection = this.__rbManager.getSelection();
      this.setReady(Boolean(selection.length));

      const isOrganizationsSelected = this.__isGroupSelected("orgs");
      this.__myOrganizationsHB.setVisibility(isOrganizationsSelected ? "visible" : "excluded");
    },

    __isGroupSelected: function(groupKey) {
      const selection = this.__rbManager.getSelection();
      if (selection.length === 1 && selection[0].shareContextId === this.__sharingOptions[groupKey].shareContextId) {
        return true;
      }
      return false;
    },

    __getSelectedOrganizationIDs: function() {
      if (this.__isGroupSelected("orgs")) {
        return this.__myOrganizationsHB.getSelectedOrganizationIDs();
      }
      return [];
    },

    getSelectedGroups: function() {
      let groupIDs = [];
      const selection = this.__rbManager.getSelection();
      if (selection.length) {
        switch (selection[0].shareContextId) {
          case 0:
          case 2:
            groupIDs = [selection[0].gid];
            break;
          case 1:
            groupIDs = this.__getSelectedOrganizationIDs();
            break;
        }
      }
      return groupIDs;
    }
  }
});
