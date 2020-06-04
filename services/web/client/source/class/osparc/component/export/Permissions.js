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
 *
 */

qx.Class.define("osparc.component.export.Permissions", {
  extend: osparc.component.export.ShareResourceBase,

  construct: function(studyId) {
    this.base(arguments, studyId);

    this._shareWith.showPrivate(false);

    this.setHeaderText(this.tr("Share with"));
    this.setButtonText(this.tr("Share"));
  },
  members: {
    createWindow: function() {
      return osparc.component.export.ShareResourceBase.createWindow(this.tr("Permissions"), this);
    },

    // overridden
    _shareResource: function(btn) {
      btn.setFetching(true);

      const shareWith = {};
      const selectedGroupIDs = this._shareWith.getSelectedGroups();
      selectedGroupIDs.forEach(gid => {
        shareWith[gid] = {
          "read": true,
          "write": true,
          "execute": false
        };
      });

      const params = {
        url: {
          "study_id": this._studyId
        },
        data: shareWith
      };
      osparc.data.Resources.fetch("studies", "share", params)
        .then(template => {
          this.fireDataEvent("finished", template);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("Study successfully shared."), "INFO");
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while sharing the study."), "ERROR");
        })
        .finally(() => {
          btn.setFetching(false);
        });
    }
  }
});
