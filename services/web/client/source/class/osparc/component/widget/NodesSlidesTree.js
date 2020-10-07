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

qx.Class.define("osparc.component.widget.NodesSlidesTree", {
  extend: osparc.component.widget.NodesTree,

  construct: function() {
    this.base(arguments);

    this.__buildLayout();
  },

  members: {
    __slidesTree: null,

    __buildLayout: function() {
      // this.__slidesTree = this._createChildControlImpl("tree");
      // this.populateTree(this.__slidesTree);

      this.__tree = this._createChildControlImpl("tree");
      this.populateTree(this.__tree);
    }
  }
});
