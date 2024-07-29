/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.ListButtonNew", {
  extend: osparc.dashboard.ListButtonBase,

  construct: function(title, description) {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.NEW);

    this.set({
      appearance: "pb-new"
    });

    if (title) {
      const titleLabel = this.getChildControl("title");
      titleLabel.set({
        value: title,
        rich: true
      });
    }

    if (description) {
      const descLabel = this.getChildControl("description");
      descLabel.setValue(description);
    }

    this.setIcon(osparc.dashboard.CardBase.NEW_ICON);
  },

  members: {
    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function(data) {
      return false;
    },

    _shouldReactToFilter: function(data) {
      return false;
    }
  }
});
