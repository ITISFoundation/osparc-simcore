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
      store.getProductEveryone()
    ])
      .then(values => {
        const groupMe = values[0];
        const groupProductEveryone = values[1];
        this.__rbManager.getChildren().forEach(rb => {
          if (rb.contextId === this.self().SharingOpts["me"].contextId) {
            rb.gid = groupMe["gid"];
          }
          if (rb.contextId === this.self().SharingOpts["productAll"].contextId) {
            // Only users  the product group can share for everyone
            if (osparc.data.Permissions.getInstance().canDo("studies.template.create.productAll")) {
              rb.gid = groupProductEveryone["gid"];
              rb.show();
            }
          }
        });
      });
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
        label: "Available to all users"
      }
    }
  },

  members: {
    __rbManager: null,
    __myOrgs: null,

    __buildLayout: function() {
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
            rb.exclude();
            this._add(rb);
            break;
        }
        this.__rbManager.add(rb);
      }

      this.__rbManager.setSelection([]);

      const addCollaborators = new osparc.share.AddCollaborators(this.__serializedDataCopy);
      addCollaborators.getChildControl("intro-text").set({
        value: this.tr("Make the ") + osparc.product.Utils.getTemplateAlias() + this.tr(" also accessible to:"),
        font: "text-14"
      });
      addCollaborators.addListener("addCollaborators", e => {
        console.log("addCollaborators", e.getData());
        // show selected list, it will be consumed by getSelectedGroups
      }, this);
      this._add(addCollaborators);
    },

    getSelectedGroups: function() {
      // whatever was selected in AddCollaborators
      let groupIDs = [];
      const selections = this.__rbManager.getSelection();
      if (selections.length) {
        const selection = selections[0];
        switch (selection.contextId) {
          case this.self().SharingOpts["me"].contextId:
          case this.self().SharingOpts["productAll"].contextId:
            groupIDs = [selection.gid];
            break;
          case this.self().SharingOpts["orgs"].contextId:
            groupIDs = this.__myOrgs.getSelectedOrgIDs();
            break;
        }
      }
      return groupIDs;
    }
  }
});
