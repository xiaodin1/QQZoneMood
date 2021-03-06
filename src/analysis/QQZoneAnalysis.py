import re
import json
import pandas as pd
import jieba
from wordcloud import WordCloud, ImageColorGenerator, STOPWORDS
from scipy.misc import imread
import matplotlib.pyplot as plt
from src.spider.QQZoneFriendSpider import QQZoneFriendSpider
from src.analysis.Average import Average
from src.util.constant import BASE_DIR, HISTORY_LIKE_AGREE


class QQZoneAnalysis(QQZoneFriendSpider):
    def __init__(self, use_redis=False, debug=False, username='', analysis_friend=False, mood_begin=0, mood_num=-1,
                 stop_time='-1', from_web=True, nickname='', no_delete=True, cookie_text='', pool_flag='127.0.0.1'):

        QQZoneFriendSpider.__init__(self, use_redis, debug, recover=False, username=username, mood_num=mood_num,
                              mood_begin=mood_begin, stop_time=stop_time, from_web=from_web, nickname=nickname,
                              no_delete=no_delete, cookie_text=cookie_text, analysis=True, export_excel=True, export_csv=False, pool_flag=pool_flag)
        self.mood_data = []
        self.mood_data_df = pd.DataFrame()
        self.like_detail_df = []
        self.like_list_names_df = []
        self.file_name_head = username
        self.analysis_friend = analysis_friend
        self.has_clean_data = False
        self.friend_dir = BASE_DIR + self.file_name_head + '/friend/' + 'friend_detail_list.csv'
        self.history_like_agree_file_name = BASE_DIR +  self.file_name_head + '/friend/' + 'history_like_list.json'

        self.av = Average(use_redis=False, file_name_head=username, analysis=True, debug=debug)
        self.init_analysis_path()

    def init_analysis_path(self):
        RESULT_BASE_DIR = self.USER_BASE_DIR + "data/result/"
        self.MOOD_DATA_FILE_NAME = RESULT_BASE_DIR + 'mood_data.csv'
        self.MOOD_DATA_EXCEL_FILE_NAME = RESULT_BASE_DIR + 'mood_data.xlsx'

        LABEL_BASE_DIR = self.USER_BASE_DIR + "data/label/"
        self.LABEL_FILE_CSV = LABEL_BASE_DIR + 'label_data.csv'
        self.LABEL_FILE_EXCEL = LABEL_BASE_DIR + 'label_data.xlsx'

        self.label_path = self.USER_BASE_DIR + 'data/label/'
        self.image_path = self.USER_BASE_DIR + '/image/'

    def load_file_from_redis(self):
        self.do_recover_from_exist_data()

    def save_data_to_csv(self):
        pd.DataFrame(self.mood_data_df).to_csv(self.MOOD_DATA_FILE_NAME)

    def save_data_to_excel(self):
        pd.DataFrame(self.mood_data_df).to_excel(self.MOOD_DATA_EXCEL_FILE_NAME)

    def load_mood_data(self):
        try:
            self.mood_data_df = pd.read_csv(self.MOOD_DATA_FILE_NAME)
            self.mood_data_df['uin_list'] = self.mood_data_df['uin_list'].apply(
                lambda x: json.loads(x.replace('\'', '\"')))
        except:
            try:
                self.mood_data_df = pd.read_excel(self.MOOD_DATA_EXCEL_FILE_NAME)
                self.mood_data_df['uin_list'] = self.mood_data_df['uin_list'].apply(
                    lambda x: json.loads(x.replace('\'', '\"')))
            except BaseException as e:
                print("加载mood_data_df失败，开始重新清洗数据")
                self.get_useful_info_from_json()

    def get_useful_info_from_json(self):
        """
        从原始动态数据中清洗出有用的信息
        结果存储在self.mood_data_df中
        :return:
        """

        self.load_file_from_redis()
        for i in range(len(self.mood_details)):
            self.parse_mood_detail(self.mood_details[i])

        for i in range(len(self.like_list_names)):
            self.parse_like_names(self.like_list_names[i])

        for i in range(len(self.like_detail)):
            self.parse_like_and_prd(self.like_detail[i])

        mood_data_df = pd.DataFrame(self.mood_data)
        like_detail_df = pd.DataFrame(self.like_detail_df)
        like_list_df = pd.DataFrame(self.like_list_names_df)
        data_df = pd.merge(left=mood_data_df, right=like_detail_df, how='inner', left_on='tid', right_on='tid')
        data_df = pd.merge(left=data_df, right=like_list_df, how='inner', left_on='tid', right_on='tid')

        data_df = data_df.sort_values(by='time_stamp', ascending=False).reset_index()

        data_df.drop(['total_num', 'index'], axis=1, inplace=True)
        # data_df.drop_duplicate()
        n_E = self.av.calculate_E(data_df)
        mood_data_df['n_E'] = n_E
        mood_data_df['user'] = self.file_name_head
        self.mood_data_df = data_df
        self.has_clean_data = True

    def parse_mood_detail(self, mood):
        try:
            msglist = json.loads(mood)
        except BaseException:
            msglist = mood
        tid = msglist['tid']
        try:
            secret = msglist['secret']
            # 过滤私密说说
            if secret:
                pass
            else:
                content = msglist['content']
                time = msglist['createTime']
                time_stamp = msglist['created_time']

                if 'pictotal' in msglist:
                    pic_num = msglist['pictotal']
                else:
                    pic_num = 0
                cmt_num = msglist['cmtnum']
                cmt_list = []
                cmt_total_num = cmt_num
                if 'commentlist' in msglist:
                    comment_list = msglist['commentlist'] if msglist['commentlist'] is not None else []

                    for i in range(len(comment_list)):
                        try:
                            comment = comment_list[i]
                            comment_content = comment['content']
                            if i < 20:
                                comment_name = comment['name']
                                comment_time = comment['createTime2']
                                comment_reply_num = comment['replyNum']
                                comment_reply_list = []
                                if comment_reply_num > 0:
                                    for comment_reply in comment['list_3']:
                                        comment_reply_content = comment_reply['content']
                                        # 去掉 @{uin:117557,nick:16,who:1,auto:1} 这种文字
                                        comment_reply_content = \
                                            re.subn(re.compile('\@\{.*?\}'), '', comment_reply_content)[
                                                0].strip()
                                        comment_reply_name = comment_reply['name']
                                        comment_reply_time = comment_reply['createTime2']
                                        comment_reply_list.append(dict(comment_reply_content=comment_reply_content,
                                                                       comment_reply_name=comment_reply_name,
                                                                       comment_reply_time=comment_reply_time))
                            else:
                                comment_name = comment['poster']['name']
                                comment_time = comment['postTime']
                                comment_reply_num = comment['extendData']['replyNum']
                                comment_reply_list = []
                                if comment_reply_num > 0:
                                    for comment_reply in comment['replies']:
                                        comment_reply_content = comment_reply['content']
                                        # 去掉 @{uin:117557,nick:16,who:1,auto:1} 这种文字
                                        comment_reply_content = \
                                            re.subn(re.compile('\@\{.*?\}'), '', comment_reply_content)[
                                                0].strip()
                                        comment_reply_name = comment_reply['poster']['name']
                                        comment_reply_time = comment_reply['postTime']
                                        comment_reply_list.append(dict(comment_reply_content=comment_reply_content,
                                                                       comment_reply_name=comment_reply_name,
                                                                       comment_reply_time=comment_reply_time))

                            cmt_total_num += comment_reply_num
                            cmt_list.append(
                                dict(comment_content=comment_content, comment_name=comment_name,
                                     comment_time=comment_time,
                                     comment_reply_num=comment_reply_num, comment_reply_list=comment_reply_list))
                        except BaseException as e:
                            self.format_error(e, comment)

                if self.analysis_friend:
                    try:
                        if self.friend_df.empty:
                            self.friend_df = pd.read_csv(self.FRIEND_DETAIL_LIST_FILE_NAME)
                        friend_num = self.calculate_friend_num_timeline(time_stamp, self.friend_df)

                    except BaseException as e:
                        print("暂无好友数据，请先运行QQZoneFriendSpider")
                        friend_num = -1

                else:
                    friend_num = -1
                self.mood_data.append(dict(tid=tid, content=content, time=time, time_stamp=time_stamp, pic_num=pic_num,
                                           cmt_num=cmt_num,
                                           cmt_total_num=cmt_total_num,
                                           cmt_list=cmt_list, friend_num=friend_num))
        except BaseException as e:
            self.format_error(e, "Error in parse mood:" + str(msglist))
            self.mood_data.append(dict(tid=tid, content=msglist['message'], time="", time_stamp="", pic_num=0,
                                       cmt_num=0,
                                       cmt_total_num=0,
                                       cmt_list=[], friend_num=-1))

    def parse_like_and_prd(self, like):
        try:
            data = like['data'][0]
            current = data['current']
            key = current['key'].split('/')[-1]
            newdata = current['newdata']
            # 点赞数
            if 'LIKE' in newdata:
                like_num = newdata['LIKE']
                # 浏览数
                prd_num = newdata['PRD']

                if self.debug:
                    if key == like['tid']:
                        print("correct like tid")
                    else:
                        print("wrong like tid")
                self.like_detail_df.append(dict(tid=like['tid'], like_num=like_num, prd_num=prd_num))
            else:
                self.like_detail_df.append(dict(tid=like['tid'], like_num=0, prd_num=0))
        except BaseException as e:
            print(like)
            self.format_error(e, 'Error in like, return 0')
            self.like_detail_df.append(dict(tid=like['tid'], like_num=0, prd_num=0))

    def parse_like_names(self, like):
        try:
            data = like['data']
            total_num = data['total_number']
            like_uin_info = data['like_uin_info']
            uin_list = []

            for uin in like_uin_info:
                nick = uin['nick']
                gender = uin['gender']
                uin_list.append(dict(nick=nick, gender=gender))
            self.like_list_names_df.append(dict(total_num=total_num, uin_list=uin_list, tid=like['tid']))
        except BaseException as e:
            self.format_error(e, "Error in parse like names")
            self.like_list_names_df.append(dict(total_num=0, uin_list=[], tid=like['tid']))

    def drawWordCloud(self, word_text, filename, dict_type=False):
        mask = imread('image/tom2.jpeg')
        my_wordcloud = WordCloud(
            background_color='white',  # 设置背景颜色
            mask=mask,  # 设置背景图片
            max_words=2000,  # 设置最大现实的字数
            stopwords=STOPWORDS,  # 设置停用词
            font_path='/System/Library/Fonts/Hiragino Sans GB.ttc',  # 设置字体格式，如不设置显示不了中文
            max_font_size=50,  # 设置字体最大值
            random_state=30,  # 设置有多少种随机生成状态，即有多少种配色方案
            scale=1.3
        )
        if not dict_type:
            my_wordcloud = my_wordcloud.generate(word_text)
        else:
            my_wordcloud = my_wordcloud.fit_words(word_text)
        image_colors = ImageColorGenerator(mask)
        my_wordcloud.recolor(color_func=image_colors)
        # 以下代码显示图片
        plt.imshow(my_wordcloud)
        plt.axis("off")
        # 保存图片
        my_wordcloud.to_file(filename=self.image_path + filename + '.jpg')
        plt.show()

    def get_jieba_words(self, content):
        word_list = jieba.cut(content, cut_all=False)
        word_list2 = []
        # waste_words = "现在 时候 这里 那里 今天 明天 非常 出去 各种 其实 真是 有点 只能 有些 只能 小时 baidu 还好 回到 好多 好的 继续 不会 起来 虽然 然饿 幸好一个 一些 一下 一样 一堆 所有 这样 那样 之后 只是 每次 所以 为了 还有 这么 那么 个人 因为 每次 但是 不想 出来 的话 这种 那种 开始 觉得 这个 那个 几乎 最后 自己 这些 那些 总之 " \
        #               "有没有 没有 并且 然后 随便 可以 太大 应该 uin nick  真的 真好 可以 不要是不是 真的或者 可以之前 不能突然最近颇极十分就都马上立刻曾经居然重新" \
        #               "不断已已经曾曾经刚刚正在将要、就、就要、马上、立刻、顿时、终于、常、常常、时常、时时、往往、渐渐、早晚、从来、终于、一向、向来、从来、总是、始终、" \
        #               "水、赶紧、仍然、还是、屡次、依然、重新、还、再、再三、偶尔都、总、共、总共、统统、只、仅仅、单、净、光、一齐、一概、一律、单单、就大肆、肆意、特意、" \
        #               "亲自、猛然、忽然、公然、连忙、赶紧、悄悄、暗暗、大力、稳步、阔步、单独、亲自难道、岂、究竟、偏偏、索性、简直、就、可、也许、难怪、大约、幸而、幸亏、" \
        #               "反倒、反正、果然、居然、竟然、何尝、何必、明明、恰恰、未免、只好、不妨"

        with open('../../resource/中文停用词库.txt', 'r', encoding='gbk') as r:
            waste_words = r.readlines()
        waste_words = list(map(lambda x: x.strip(), waste_words))
        waste_words.extend(['uin', 'nick'])
        waste_words = set(waste_words)
        for word in word_list:
            if len(word) >= 2 and word.find('e') == -1 and word not in waste_words:
                word_list2.append(word)
        words_text = " ".join(word_list2)
        return words_text

    def calculate_content_cloud(self, df):
        content = df['content'].sum()

        words = self.get_jieba_words(content)
        self.drawWordCloud(words, self.file_name_head + '_content_')

    def calculate_cmt_cloud(self, df):
        cmt_df = self.av.calculate_cmt_rank(df)
        cmt_dict = {x[0]: x[1] for x in cmt_df.values}
        self.drawWordCloud(cmt_dict, self.file_name_head + '_cmt_', dict_type=True)

    def rank_like_people(self, df):
        uin_list = df['uin_list']
        all_uin_list = []
        for item in uin_list:
            all_uin_list.extend(item)
        all_uin_df = pd.DataFrame(all_uin_list)
        all_uin_count = all_uin_df.groupby(['nick']).count().reset_index()
        return all_uin_count

    def calculate_like_cloud(self, df):
        all_uin_count = self.rank_like_people(df)
        all_uin_dict = {str(x[0]): x[1] for x in all_uin_count.values}
        self.drawWordCloud(all_uin_dict, self.file_name_head + '_like_', dict_type=True)

    def export_mood_df(self, export_csv=True, export_excel=True):
        """
        根据传入的文件名前缀清洗原始数据，导出csv和excel表
        :param file_name_head:
        :param export_csv:
        :param export_excel:
        :return:
        """
        if not self.has_clean_data:
            self.get_useful_info_from_json()
        if export_csv:
            self.save_data_to_csv()
        if export_excel:
            self.save_data_to_excel()
        print("保存清洗后的数据成功", self.username)

    def get_most_people(self):
        if not self.has_clean_data:
            self.get_useful_info_from_json()
        all_uin_count = self.rank_like_people(self.mood_data_df)
        all_uin_count = all_uin_count.sort_values(by="gender", ascending=False).reset_index()
        most_like_name = all_uin_count.loc[0, 'nick']

        cmt_df = self.av.calculate_cmt_rank(self.mood_data_df).reset_index()
        most_cmt_name = cmt_df.loc[0, 'cmt_name']
        self.user_info.cmt_friend_name = most_cmt_name
        self.user_info.like_friend_name = most_like_name
        self.user_info.save_user()

    def calculate_history_like_agree(self):
        history_df = self.mood_data_df.loc[:, ['cmt_total_num', 'like_num', 'content', 'time']]
        history_json = history_df.to_json(orient='records', force_ascii=False)
        if self.use_redis:
            self.re.set(self.history_like_agree_file_name, json.dumps(history_json, ensure_ascii=False))
        else:
            self.save_data_to_json(history_json, self.history_like_agree_file_name)

def clean_label_data():
    new_list = ['maicius']
    for name in new_list:
        print(name + '====================')
        analysis = QQZoneAnalysis(use_redis=True, debug=True, username=name, analysis_friend=False)
        # print(analysis.check_data_shape())
        analysis.get_useful_info_from_json()
        analysis.save_data_to_csv()
        # analysis.save_data_to_excel()
        # analysis.export_label_data(analysis.mood_data_df)
        # analysis.calculate_content_cloud(analysis.mood_data_df)
        # analysis.calculate_cmt_cloud(analysis.mood_data_df)
        analysis.calculate_like_cloud(analysis.mood_data_df)
        # analysis.export_all_label_data()

def get_most_people(username):
    analysis = QQZoneAnalysis(use_redis=True, debug=True, username=username, analysis_friend=False, from_web=True)
    analysis.get_most_people()

def export_mood_df(username):
    analysis = QQZoneAnalysis(use_redis=True, debug=True, username=username, analysis_friend=False, from_web=True)
    analysis.export_mood_df()



if __name__ == '__main__':
    export_mood_df("1272082503")
    get_most_people("1272082503")
    # clean_label_data()
