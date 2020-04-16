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

  construct: function(filterGroupId) {
    this.base(arguments, this.tr("Share with"));

    this.set({
      appearance: "settings-groupbox",
      layout: new qx.ui.layout.VBox(10)
    });

    this.__buildLayout(filterGroupId);
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
      "private": {
        shareContextId: 0,
        label: "Private"
      },
      "organization": {
        shareContextId: 1,
        label: "Organizations"
      },
      "all": {
        shareContextId: 2,
        label: "All"
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
        if (sharingOptionKey === "organization") {
          const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
          const myOrganizationsHB = this.__myOrganizationsHB = new osparc.component.filter.Organizations(filterGroupId);
          vBox.add(rb);
          vBox.add(myOrganizationsHB);
          this.add(vBox);
        } else {
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

      const isOrganizationsSelected = this.__isOrganizationsSelected();
      this.__myOrganizationsHB.setVisibility(isOrganizationsSelected ? "visible" : "excluded");
    },

    __isOrganizationsSelected: function() {
      const selection = this.__rbManager.getSelection();
      if (selection.length === 1 && selection[0].shareContextId === this.__sharingOptions["organization"].shareContextId) {
        return true;
      }
      return false;
    },

    getShareWithId: function() {
      const selection = this.__rbManager.getSelection();
      if (selection.length) {
        return selection[0].shareContextId;
      }
      return null;
    },

    getSelectedOrganizationIDs: function() {
      if (this.__isOrganizationsSelected()) {
        return this.__myOrganizationsHB.getSelectedOrganizationIDs();
      }
      return [];
    }
  }
});
