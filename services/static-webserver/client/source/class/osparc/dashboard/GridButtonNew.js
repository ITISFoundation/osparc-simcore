/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Tobias Oetiker (oetiker)

************************************************************************ */

/* eslint "qx-rules/no-refs-in-members": "warn" */

/**
 * Widget used mainly by StudyBrowser for displaying Studies
 *
 * It consists of a thumbnail and creator and last change as caption
 */

qx.Class.define("osparc.dashboard.GridButtonNew", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function(title, description) {
    this.base(arguments);

    this.setPriority(osparc.dashboard.CardBase.CARD_PRIORITY.NEW);

    this._buildLayout();

    if (title) {
      const titleLabel = this.getChildControl("title");
      titleLabel.setValue(title);
    }

    if (description) {
      const descLabel = this.getChildControl("subtitle-text");
      descLabel.setValue(description.toString());
    }
  },

  members: {
    _buildLayout: function() {
      const title = this.getChildControl("title");
      title.setValue(this.tr("Empty") + " " + osparc.product.Utils.getStudyAlias({
        firstUpperCase: true
      }));

      const desc = this.getChildControl("subtitle-text");
      desc.setValue(this.tr("Start with an empty study").toString());

      this.setIcon(osparc.dashboard.CardBase.NEW_ICON);
    },

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
