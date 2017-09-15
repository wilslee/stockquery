# coding:utf-8
import requests  # Python 第三方库


def get_hs_stock(gid):
    url = 'http://web.juhe.cn:8080/finance/stock/hs'
    params = {
        'gid': gid,
        'key': 'bb8a976aab11325ea23006f32c9a7d16'
    }
    resp = requests.get(url, params=params)
    # print(resp)
    # print(resp.json())
    query_result = ''
    if resp.status_code == 200:
        resp_data = resp.json()
        # print(resp_data)
        error_code = resp_data.get('error_code')
        if error_code == 0:
            result = resp_data.get('result')
            data = result[0].get('data')
            now_price = data.get('nowPri')
            name = data.get('name')
            query_result = '{}({}) 当前的股票价格是: {}'.format(name, gid, now_price)
        elif error_code == 202101:
            query_result = '参数错误'
        elif error_code == 202102:
            query_result = '{} 查询不到结果'.format(gid)
        elif error_code == 202103:
            query_result = '网络异常'
        else:
            query_result = '{}: {}'.format(error_code, resp_data.get('reason'))
    else:
        query_result = '请求错误，错误代码 {}'.format(resp.status_code)
    return query_result
