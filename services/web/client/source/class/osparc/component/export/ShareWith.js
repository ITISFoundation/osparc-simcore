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
          if (rb.contextId === this.__sharingOpts["me"].contextId) {
            rb.gid = groupMe["gid"];
          }
          if (rb.contextId === this.__sharingOpts["all"].contextId) {
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
    __sharingOpts: {
      "me": {
        contextId: 0,
        label: "Private"
      },
      /*
      "orgMembers": {
        contextId: 1,
        label: "Organization Members"
      },
      */
      "orgs": {
        contextId: 2,
        label: "Organizations"
      },
      "all": {
        contextId: 3,
        label: "Everyone"
      }
    },
    __rbManager: null,
    __privateLayout: null,
    __publicLayout: null,
    __myOrgMembersHB: null,
    __myOrgMembers: null,
    __myOrgs: null,

    __buildLayout: function() {
      this.__rbManager = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });

      for (let [sharingOptionKey, sharingOption] of Object.entries(this.__sharingOpts)) {
        const rb = new qx.ui.form.RadioButton(sharingOption.label);
        rb.contextId = sharingOption.contextId;
        switch (sharingOptionKey) {
          case "me":
            this.__privateLayout = rb;
            this.add(rb);
            break;
          case "orgMembers": {
            const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            const myOrgMembersHB = this.__myOrgMembersHB = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
              alignY: "middle"
            }));
            const myOrgsSB = new qx.ui.form.SelectBox();
            osparc.data.Resources.get("organizations")
              .then(resp => {
                const orgs = resp["organizations"];
                orgs.sort(this.__sortByLabel);
                orgs.forEach(org => {
                  const orgItem = new qx.ui.form.ListItem(org["label"]);
                  orgItem.gid = org["gid"];
                  myOrgsSB.add(orgItem);
                });
              });
            myOrgMembersHB.add(myOrgsSB);
            const myOrgMembers = this.__myOrgMembers = new osparc.component.filter.OrganizationMembers("asdfasdf");
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
            const myOrgs = this.__myOrgs = new osparc.component.filter.Organizations();
            vBox.add(rb);
            vBox.add(myOrgs);
            this.add(vBox);
            break;
          }
          case "all":
            this.__publicLayout = rb;
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

      // this.__myOrgMembersHB.setVisibility(this.__isGroupSelected("orgMembers") ? "visible" : "excluded");
      this.__myOrgs.setVisibility(this.__isGroupSelected("orgs") ? "visible" : "excluded");
    },

    __isGroupSelected: function(groupKey) {
      const selection = this.__rbManager.getSelection();
      if (selection.length === 1 && selection[0].contextId === this.__sharingOpts[groupKey].contextId) {
        return true;
      }
      return false;
    },

    __getSelectedOrgMemberIDs: function() {
      if (this.__isGroupSelected("orgMembers")) {
        return this.__myOrgMembers.getSelectedOrgMemberIDs();
      }
      return [];
    },

    __getSelectedOrgIDs: function() {
      if (this.__isGroupSelected("orgs")) {
        return this.__myOrgs.getSelectedOrgIDs();
      }
      return [];
    },

    showPrivate: function(show) {
      this.__privateLayout.setVisibility(show ? "visible" : "excluded");
    },

    showPublic: function(show) {
      this.__publicLayout.setVisibility(show ? "visible" : "excluded");
    },

    getSelectedGroups: function() {
      let groupIDs = [];
      const selection = this.__rbManager.getSelection();
      if (selection.length) {
        switch (selection[0].contextId) {
          case this.__sharingOpts["me"].contextId:
          case this.__sharingOpts["all"].contextId:
            groupIDs = [selection[0].gid];
            break;
          case this.__sharingOpts["orgMembers"].contextId:
            groupIDs = this.__getSelectedOrgMemberIDs();
            break;
          case this.__sharingOpts["orgs"].contextId:
            groupIDs = this.__getSelectedOrgIDs();
            break;
        }
      }
      return groupIDs;
    }
  }
});
