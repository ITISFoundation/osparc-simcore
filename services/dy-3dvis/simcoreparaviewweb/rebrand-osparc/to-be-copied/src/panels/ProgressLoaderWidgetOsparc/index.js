import React from 'react';
import PropTypes from 'prop-types';

import style from './ProgressLoaderWidgetOsparc.mcss';

export default function ProgressLoaderWidgetOsparc(props) {
  return (
    <div className={style.container}>
      <div className={style.loader} />
      <div className={style.message}>{props.message}</div>
      <div className={style.imageLogo} />​
    </div>
  );
}

ProgressLoaderWidgetOsparc.propTypes = {
  message: PropTypes.string,
};

ProgressLoaderWidgetOsparc.defaultProps = {
  message: 'Loading oSPARC...',
};
