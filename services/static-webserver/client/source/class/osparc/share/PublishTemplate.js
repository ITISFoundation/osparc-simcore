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
 * View that shows template publishing sharing options:
 * - Private
 * - My organizations
 * - Product everyone
 * - Everyone
 */

qx.Class.define("osparc.share.PublishTemplate", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();

    const store = osparc.store.Store.getInstance();
    Promise.all([
      store.getGroupsMe(),
      store.getProductEveryone(),
      store.getGroupEveryone()
    ])
      .then(values => {
        const groupMe = values[0];
        const groupProductEveryone = values[1];
        const groupEveryone = values[2];
        this.__rbManager.getChildren().forEach(rb => {
          if (rb.contextId === this.self().SharingOpts["me"].contextId) {
            rb.gid = groupMe["gid"];
          }
          if (rb.contextId === this.self().SharingOpts["productAll"].contextId) {
            // Only users  the product group can share for everyone
            if (groupProductEveryone) {
              rb.gid = groupProductEveryone["gid"];
              rb.show();
            }
          }
          if (rb.contextId === this.self().SharingOpts["all"].contextId) {
            if (osparc.data.Permissions.getInstance().canDo("studies.template.create.all")) {
              rb.gid = groupEveryone["gid"];
              rb.show();
            }
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

  statics: {
    SharingOpts: {
      "me": {
        contextId: 0,
        label: "Private"
      },
      "orgs": {
        contextId: 1,
        label: "Organizations"
      },
      "productAll": {
        contextId: 2,
        label: "Public for Product users"
      },
      "all": {
        contextId: 3,
        label: "Public"
      }
    }
  },

  members: {
    __rbManager: null,
    __myOrgs: null,

    __buildLayout: function() {
      this._add(new qx.ui.basic.Label().set({
        value: this.tr("Make the ") + osparc.product.Utils.getTemplateAlias() + this.tr(" accessible to:"),
        font: "text-14"
      }));

      this.__rbManager = new qx.ui.form.RadioGroup().set({
        allowEmptySelection: true
      });

      for (let [sharingOptionKey, sharingOption] of Object.entries(this.self().SharingOpts)) {
        const rb = new qx.ui.form.RadioButton(sharingOption.label);
        rb.contextId = sharingOption.contextId;
        switch (sharingOptionKey) {
          case "me":
            this._add(rb);
            break;
          case "orgs": {
            const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox());
            const myOrgs = this.__myOrgs = new osparc.filter.Organizations();
            vBox.add(rb);
            vBox.add(myOrgs);
            this._add(vBox);
            break;
          }
          case "productAll":
          case "all":
            rb.exclude();
            this._add(rb);
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

      this.__myOrgs.setVisibility(this.__isGroupSelected("orgs") ? "visible" : "excluded");
    },

    __isGroupSelected: function(groupKey) {
      const selection = this.__rbManager.getSelection();
      if (selection.length === 1 && selection[0].contextId === this.self().SharingOpts[groupKey].contextId) {
        return true;
      }
      return false;
    },

    __getSelectedOrgIDs: function() {
      if (this.__isGroupSelected("orgs")) {
        return this.__myOrgs.getSelectedOrgIDs();
      }
      return [];
    },

    getSelectedGroups: function() {
      let groupIDs = [];
      const selection = this.__rbManager.getSelection();
      if (selection.length) {
        switch (selection[0].contextId) {
          case this.self().SharingOpts["me"].contextId:
          case this.self().SharingOpts["orgs"].contextId:
            groupIDs = this.__getSelectedOrgIDs();
            break;
          case this.self().SharingOpts["all"].contextId:
            groupIDs = [selection[0].gid];
            break;
        }
      }
      return groupIDs;
    }
  }
});
