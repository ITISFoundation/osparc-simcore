/* ************************************************************************

   osparc - the simcore frontend

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
qx.Class.define("osparc.filter.NodeTypeFilter", {
  extend: osparc.filter.TagsFilter,

  /**
   * Constructor for NodeTypeFilter creates the filter and builds its menu.
   *
   * @extends osparc.filter.TagsFilter
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments, this.tr("Node types"), filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.HBox());

    this.__buildMenu();
  },

  members: {
    /**
     * Function that uses the information in {osparc.utils.Services} statics to build the menu for the filter.
     */
    __buildMenu: function() {
      osparc.utils.Services.getTypes().forEach(serviceType => this._addOption(osparc.utils.Utils.capitalize(serviceType)));
    }
  }
});
