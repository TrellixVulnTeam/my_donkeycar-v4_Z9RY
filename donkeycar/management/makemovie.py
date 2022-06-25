import moviepy.editor as mpy
from tensorflow.python.keras import activations
from tensorflow.python.keras import backend as K
import tensorflow as tf
import cv2
from matplotlib import cm
try:
    from vis.utils import utils
except:
    raise Exception("Please install keras-vis: pip install git+https://github.com/autorope/keras-vis.git")

import donkeycar as dk
from donkeycar.parts.tub_v2 import Tub
from donkeycar.utils import *


DEG_TO_RAD = math.pi / 180.0


class MakeMovie(object):

    def run(self, args, parser):
        '''
        Load the images from a tub and create a movie from them.
        Movie
        '''

        if args.tub is None:
            print("ERR>> --tub argument missing.")
            parser.print_help()
            return

        conf = os.path.expanduser(args.config)
        if not os.path.exists(conf):
            print("No config file at location: %s. Add --config to specify\
                 location or run from dir containing config.py." % conf)
            return

        self.cfg = dk.load_config(conf)

        if args.type is None and args.model is not None:
            args.type = self.cfg.DEFAULT_MODEL_TYPE
            print("Model type not provided. Using default model type from config file")

        if args.salient:
            if args.model is None:
                print("ERR>> salient visualization requires a model. Pass with the --model arg.")
                parser.print_help()

            if args.type not in ['linear', 'categorical']:
                print("Model type {} is not supported. Only linear or categorical is supported for salient visualization".format(args.type))
                parser.print_help()
                return

        self.model_type = args.type
        self.tub = Tub(args.tub)

        start = args.start
        self.end_index = args.end if args.end != -1 else len(self.tub)
        num_frames = self.end_index - start

        # Move to the correct offset
        self.current = 0
        self.iterator = self.tub.__iter__()
        while self.current < start:
            self.iterator.next()
            self.current += 1

        self.scale = args.scale
        self.keras_part = None
        self.do_salient = False
        self.user = args.draw_user_input
        if args.model is not None:
            self.keras_part = get_model_by_type(args.type, cfg=self.cfg)
            self.keras_part.load(args.model)
            if args.salient:
                self.do_salient = self.init_salient(self.keras_part.interpreter.model)

        print('making movie', args.out, 'from', num_frames, 'images')
 
        import csv
        try:
            f = open(self.cfg.DATA_PATH + '/log.csv','r')
            self.csv = [row for row in csv.reader(f)]

            row = self.csv[0]
            n = 0
            self.dic = {}
            for d in row:
                self.dic[row[n]] = n
                n += 1

            n = 1
            self.duration = 0
            for d in self.csv:
                row = self.csv[n]
                self.duration += float(row[1])
            self.duration /= 1000
            self.csv_file = True
        except:
            print("open log.csv error")
            self.csv_file = False

        if not self.csv_file:
            clip = mpy.VideoClip(self.make_frame, duration=((num_frames - 1) / self.cfg.DRIVE_LOOP_HZ))
            clip.write_videofile(args.out, fps=self.cfg.DRIVE_LOOP_HZ)
        else:
            clip = mpy.VideoClip(self.make_frame, duration=self.duration)
            clip.write_videofile(args.out, fps=(num_frames - 1) / self.duration)

    @staticmethod
    def draw_line_into_image(angle, throttle, is_left, img, color):
        import cv2

        height, width, _ = img.shape
        '''
        length = height
        a1 = angle * 45.0
        l1 = throttle * length
        mid = width // 2 + (- 1 if is_left else +1)

        p1 = tuple((mid - 2, height - 1))
        p11 = tuple((int(p1[0] + l1 * math.cos((a1 + 270.0) * DEG_TO_RAD)),
                     int(p1[1] + l1 * math.sin((a1 + 270.0) * DEG_TO_RAD))))
        '''
        p1 = tuple((int(round(width/2)), int(round(height))))
        p11 = tuple((int(round(width/2 + width/2 * angle)),
                    int(round(height + height * throttle))))

        cv2.line(img, p1, p11, color, 2)

    def draw_user_input(self, record, img, img_drawon):
        """
        Draw the user input as a green line on the image
        """
        user_angle = float(record["user/angle"])
        user_throttle = float(record["user/throttle"])

        try:
            if record["user/mode"] == "local_angle":
                user_angle = float(record["pilot/angle"])
            elif record["user/mode"] == "local":
                user_angle = float(record["pilot/angle"])
                user_throttle = float(record["pilot/throttle"])
        except:
            pass

        user_angle *= (1 if self.cfg.SBUS_CH1_MIN < self.cfg.SBUS_CH1_MAX else -1)
        user_throttle *= (1 if self.cfg.SBUS_CH2_MIN < self.cfg.SBUS_CH2_MAX else -1)

        green = (0, 255, 0)
        self.draw_line_into_image(user_angle, user_throttle, False, img_drawon, green)

        img = img_drawon
        height, width, _ = img.shape
        textFontFace = cv2.FONT_HERSHEY_SIMPLEX
        textFontScale = 0.4
        textColor = (0, 255, 0)
        #textColor = (0, 0, 255)
        textThickness = 1
        cv2.putText(img, record["user/mode"],(0,9),textFontFace,textFontScale,textColor,textThickness)
        cv2.putText(img, str(self.current),(120,9),textFontFace,textFontScale,textColor,textThickness)

        if self.csv_file == True:
            row = self.csv[self.current + 1]

            i = 1
            period_time = int(float(row[i]))
            if period_time > 99.9:
                pos = (159-3*8,height-1)
            elif period_time > 9.9:
                pos = (159-2*8,height-1)
            else:
                pos = (159-1*8,wheight-1)
            cv2.putText(img, str(period_time),pos,textFontFace,textFontScale,textColor,textThickness)
            self.duration += period_time

            i = self.dic["va"]
            volt_a = "{:.2f}".format(float(row[i]))
            cv2.putText(img, volt_a,(0,height-1),textFontFace,textFontScale,textColor,textThickness)
            i = self.dic["vb"]
            volt_b = "{:.2f}".format(float(row[i]))
            cv2.putText(img, volt_b,(0,height-11),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["lap"]
            lap = row[i]
            cv2.putText(img, lap,(0,height-21),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["kmph"]
            kmph = "{:.1f}".format(float(row[i]))
            cv2.putText(img, kmph,(40,height-1),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["rpm"]
            rpm = row[i]
            cv2.putText(img, rpm,(90,height-1),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["gyro_gain"]
            gyro_gain = row[i]
            cv2.putText(img, gyro_gain,(0,39),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["ai_throttle_mult"]
            ai_throttle_mult = "{:.2f}".format(float(row[i]))
            cv2.putText(img, ai_throttle_mult,(0,29),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["stop_range"]
            stop_range = row[i]
            cv2.putText(img, stop_range,(0,49),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["lidar"]
            lidar = row[i]
            cv2.putText(img, lidar,(0,59),textFontFace,textFontScale,textColor,textThickness)

            i = self.dic["throttle_scale"]
            throttle_scale = "{:.2f}".format(float(row[i]))
            cv2.putText(img, throttle_scale,(0,19),textFontFace,textFontScale,textColor,textThickness)

    def draw_model_prediction(self, img, img_drawon):
        """
        query the model for it's prediction, draw the predictions
        as a blue line on the image
        """
        if self.keras_part is None:
            return

        expected = tuple(self.keras_part.get_input_shapes()[0][1:])
        actual = img.shape

        # if model expects grey-scale but got rgb, covert
        if expected[2] == 1 and actual[2] == 3:
            # normalize image before grey conversion
            grey_img = rgb2gray(img)
            actual = grey_img.shape
            img = grey_img.reshape(grey_img.shape + (1,))

        if expected != actual:
            print(f"expected input dim {expected} didn't match actual dim "
                  f"{actual}")
            return

        blue = (0, 0, 255)
        pilot_angle, pilot_throttle = self.keras_part.run(img)
        self.draw_line_into_image(pilot_angle, pilot_throttle, True, img_drawon, blue)

    def draw_steering_distribution(self, img, img_drawon):
        """
        query the model for it's prediction, draw the distribution of
        steering choices, only for model type of Keras Categorical
        """
        from donkeycar.parts.keras import KerasCategorical

        if self.keras_part is None or type(self.keras_part) is not KerasCategorical:
            return        
        pred_img = normalize_image(img)
        angle_binned, _ = self.keras_part.interpreter.predict(pred_img, other_arr=None)

        x = 4
        dx = 4
        y = 120 - 4
        iArgMax = np.argmax(angle_binned)
        for i in range(15):
            p1 = (x, y)
            p2 = (x, y - int(angle_binned[i] * 100.0))
            if i == iArgMax:
                cv2.line(img_drawon, p1, p2, (255, 0, 0), 2)
            else:
                cv2.line(img_drawon, p1, p2, (200, 200, 200), 2)
            x += dx

    def init_salient(self, model):
        # Utility to search for layer index by name. 
        # Alternatively we can specify this as -1 since it corresponds to the last layer.
        output_name = []
        layer_idx = []
        for i, layer in enumerate(model.layers):
            if "dropout" not in layer.name.lower() and "out" in layer.name.lower():
                output_name.append(layer.name)
                layer_idx.append(i)

        if output_name is []:
            print("Failed to find the model layer named with 'out'. Skipping salient.")
            return False

        print("####################")
        print("Visualizing activations on layer:", output_name)
        print("####################")
        
        # ensure we have linear activation
        for li in layer_idx:
            model.layers[li].activation = activations.linear
        # build salient model and optimizer
        sal_model = utils.apply_modifications(model)
        self.sal_model = sal_model
        return True

    def compute_visualisation_mask(self, img):
        img = img.reshape((1,) + img.shape)
        images = tf.Variable(img, dtype=float)

        if self.model_type == 'linear':
            with tf.GradientTape(persistent=True) as tape:
                tape.watch(images)
                pred_list = self.sal_model(images, training=False)
        elif self.model_type == 'categorical':
            with tf.GradientTape(persistent=True) as tape:
                tape.watch(images)
                pred = self.sal_model(images, training=False)
                pred_list = []
                for p in pred:
                    maxindex = tf.math.argmax(p[0])
                    pred_list.append(p[0][maxindex])
                    
        grads = 0
        for p in pred_list:
            grad = tape.gradient(p, images)
            grads += tf.math.square(grad)
        grads = tf.math.sqrt(grads)

        channel_idx = 1 if K.image_data_format() == 'channels_first' else -1
        grads = np.sum(grads, axis=channel_idx)
        res = utils.normalize(grads)[0]
        return res

    def draw_salient(self, img):

        alpha = 0.004
        beta = 1.0 - alpha
        expected = self.keras_part.interpreter.model.inputs[0].shape[1:]
        actual = img.shape

        # check input depth and convert to grey to match expected model input
        if expected[2] == 1 and actual[2] == 3:
            grey_img = rgb2gray(img)
            img = grey_img.reshape(grey_img.shape + (1,))

        norm_img = normalize_image(img)
        salient_mask = self.compute_visualisation_mask(norm_img)
        salient_mask_stacked = cm.inferno(salient_mask)[:,:,0:3]
        salient_mask_stacked = cv2.GaussianBlur(salient_mask_stacked,(3,3),cv2.BORDER_DEFAULT)
        blend = cv2.addWeighted(img.astype('float32'), alpha, salient_mask_stacked.astype('float32'), beta, 0)
        return blend

    def make_frame(self, t):
        '''
        Callback to return an image from from our tub records.
        This is called from the VideoClip as it references a time.
        We don't use t to reference the frame, but instead increment
        a frame counter. This assumes sequential access.
        '''

        if self.current >= self.end_index:
            return None

        rec = self.iterator.next()
        img_path = os.path.join(self.tub.images_base_path, rec['cam/image_array'])
        image_input = img_to_arr(Image.open(img_path))
        image = image_input
        
        if self.do_salient:
            image = self.draw_salient(image_input)
            image = cv2.normalize(src=image, dst=None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        
        if self.user: self.draw_user_input(rec, image_input, image)
        if self.keras_part is not None:
            self.draw_model_prediction(image_input, image)
            self.draw_steering_distribution(image_input, image)

        if self.scale != 1:
            h, w, d = image.shape
            dsize = (w * self.scale, h * self.scale)
            image = cv2.resize(image, dsize=dsize, interpolation=cv2.INTER_LINEAR)
            image = cv2.GaussianBlur(image,(3,3),cv2.BORDER_DEFAULT)

        self.current += 1
        # returns a 8-bit RGB array
        return image
