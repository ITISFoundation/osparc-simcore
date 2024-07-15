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
  },

  members: {
    __selectedCollabs: null,

    __buildLayout: function() {
      const addCollaborators = new osparc.share.AddCollaborators(this.__serializedDataCopy);
      addCollaborators.getChildControl("intro-text").set({
        value: this.tr("Make the ") + osparc.product.Utils.getTemplateAlias() + this.tr(" also accessible to:"),
        font: "text-14"
      });
      this._add(addCollaborators);

      const selectedCollabs = this.__selectedCollabs = new qx.ui.container.Composite(new qx.ui.layout.HBox());
      this._add(selectedCollabs);

      addCollaborators.addListener("addCollaborators", e => {
        const gids = e.getData();
        if (gids.length) {
          osparc.store.Store.getInstance().getPotentialCollaborators(false, true)
            .then(potentialCollaborators => {
              gids.forEach(gid => {
                if (gid in potentialCollaborators) {
                  const collabButton = new qx.ui.toolbar.Button(potentialCollaborators[gid]["label"], "@MaterialIcons/close/12");
                  collabButton.gid = gid;
                  selectedCollabs.add(collabButton);
                  collabButton.addListener("execute", () => selectedCollabs.remove(collabButton));
                }
              });
            });
        }
      }, this);
    },

    getSelectedGroups: function() {
      const groupIDs = [];
      this.__selectedCollabs.getChildren().forEach(selectedCollab => groupIDs.push(selectedCollab.gid));
      return groupIDs;
    }
  }
});
