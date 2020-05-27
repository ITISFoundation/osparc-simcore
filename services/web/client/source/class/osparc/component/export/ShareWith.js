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
 * - Private
 * - Organization members
 * - My organizations
 * - Everyone
 */

qx.Class.define("osparc.component.export.ShareWith", {
  extend: qx.ui.groupbox.GroupBox,

  construct: function(header) {
    this.base(arguments, header);

    this.set({
      appearance: "settings-groupbox",
      layout: new qx.ui.layout.VBox(10)
    });

    this.__buildLayout();

    const store = osparc.store.Store.getInstance();
    Promise.all([
      store.getGroupsMe(),
      store.getGroupsAll()
    ])
      .then(values => {
        const groupMe = values[0];
        const groupAll = values[1];
        this.__rbManager.getChildren().forEach(rb => {
          if (rb.shareContextId === this.__sharingOptions["me"].shareContextId) {
            rb.gid = groupMe["gid"];
          }
          if (rb.shareContextId === this.__sharingOptions["all"].shareContextId) {
            rb.gid = groupAll["gid"];
          }
        });
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
        label: "Private"
      },
      "orgMembers": {
        shareContextId: 1,
        label: "Organization Members"
      },
      "orgs": {
        shareContextId: 2,
        label: "Organizations"
      },
      "all": {
        shareContextId: 3,
        label: "Everyone"
      }
    },
    __rbManager: null,
    __privateLayout: null,
    __myOrganizationMembersHB: null,
    __myOrganizationMembers: null,
    __myOrganizations: null,

    __buildLayout: function() {
      this.__rbManager = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });

      for (let [sharingOptionKey, sharingOption] of Object.entries(this.__sharingOptions)) {
        const rb = new qx.ui.form.RadioButton(sharingOption.label);
        rb.shareContextId = sharingOption.shareContextId;
        switch (sharingOptionKey) {
          case "me":
            this.__privateLayout = rb;
            this.add(rb);
            break;
          case "orgMembers": {
            const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            const myOrgMembersHB = this.__myOrganizationMembersHB = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
              alignY: "middle"
            }));
            const myOrgsSB = new qx.ui.form.SelectBox();
            const store = osparc.store.Store.getInstance();
            store.getGroupsOrganizations()
              .then(orgs => {
                orgs.sort(this.__sortByLabel);
                orgs.forEach(org => {
                  const orgItem = new qx.ui.form.ListItem(org["label"]);
                  orgItem.gid = org["gid"];
                  myOrgsSB.add(orgItem);
                });
              });
            myOrgMembersHB.add(myOrgsSB);
            const myOrgMembers = this.__myOrganizationMembers = new osparc.component.filter.OrganizationMembers("asdfasdf");
            myOrgMembersHB.add(myOrgMembers, {
              flex: 1
            });
            myOrgsSB.addListener("changeSelection", e => {
              myOrgMembers.setOrganizationId(e.getData()[0].gid);
            });
            vBox.add(rb);
            vBox.add(myOrgMembersHB);
            this.add(vBox);
            break;
          }
          case "orgs": {
            const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            const myOrgs = this.__myOrganizations = new osparc.component.filter.Organizations();
            vBox.add(rb);
            vBox.add(myOrgs);
            this.add(vBox);
            break;
          }
          case "all":
            this.add(rb);
            break;
        }
        this.__rbManager.add(rb);
      }

      this.__rbManager.addListener("changeSelection", this.__onChangeSelection, this);
      this.__rbManager.setSelection([]);
    },

    __onChangeSelection: function() {
      const selection = this.__rbManager.getSelection();
      this.setReady(Boolean(selection.length));

      this.__myOrganizationMembersHB.setVisibility(this.__isGroupSelected("orgMembers") ? "visible" : "excluded");
      this.__myOrganizations.setVisibility(this.__isGroupSelected("orgs") ? "visible" : "excluded");
    },

    __isGroupSelected: function(groupKey) {
      const selection = this.__rbManager.getSelection();
      if (selection.length === 1 && selection[0].shareContextId === this.__sharingOptions[groupKey].shareContextId) {
        return true;
      }
      return false;
    },

    __getSelectedOrganizationMemberIDs: function() {
      if (this.__isGroupSelected("orgMembers")) {
        return this.__myOrganizations.getSelectedOrganizationIDs();
      }
      return [];
    },

    __getSelectedOrganizationIDs: function() {
      if (this.__isGroupSelected("orgs")) {
        return this.__myOrganizations.getSelectedOrganizationIDs();
      }
      return [];
    },

    showPrivate: function(show) {
      this.__privateLayout.setVisibility(show ? "visible" : "excluded");
    },

    getSelectedGroups: function() {
      let groupIDs = [];
      const selection = this.__rbManager.getSelection();
      if (selection.length) {
        switch (selection[0].shareContextId) {
          case this.__sharingOptions["me"].shareContextId:
          case this.__sharingOptions["all"].shareContextId:
            groupIDs = [selection[0].gid];
            break;
          case this.__sharingOptions["orgMembers"].shareContextId:
            groupIDs = this.__getSelectedOrganizationMemberIDs();
            break;
          case this.__sharingOptions["orgs"].shareContextId:
            groupIDs = this.__getSelectedOrganizationIDs();
            break;
        }
      }
      return groupIDs;
    }
  }
});
