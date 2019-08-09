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
 * Defines the methods all UIFilter elements should implement.
 */
qx.Interface.define("qxapp.component.filter.IFilter", {
  members:{
    /**
     * Function in charge of resetting the filter.
     */
    reset: function() {
      this.assertArgumentsCount(arguments, 0, 0);
    }
  }
});
