import * as gulp from 'gulp';
import { join } from 'path';

import Config from '../../config';

/**
 * This sample task copies all TypeScript files over to the appropiate `dist/dev|prod|test` directory, depending on the
 * current application environment.
 */
export = () => {
  return gulp.src('node_modules/bootstrap/dist/fonts/*')
    .pipe(gulp.dest(join(Config.APP_DEST, '/fonts')));
};
