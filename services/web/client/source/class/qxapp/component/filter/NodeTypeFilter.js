/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Filter for node types.
 */
qx.Class.define("qxapp.component.filter.NodeTypeFilter", {
  extend: qxapp.component.filter.TagsFilter,

  /**
   * Constructor for NodeTypeFilter creates the filter and builds its menu.
   *
   * @extends qxapp.component.filter.UIFilter
   */
  construct: function(filterId, groupId) {
    this.base(arguments, this.tr("Tags"), filterId, groupId);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildMenu();
  },

  members: {
    __buildMenu: function() {
      qxapp.utils.Services.getTypes().forEach(serviceType => this._addOption(qxapp.utils.Utils.capitalize(serviceType)));
      this._addSeparator();
      qxapp.utils.Services.getCategories().forEach(serviceCategory => this._addOption(qxapp.utils.Utils.capitalize(serviceCategory)));
    }
  }
});
