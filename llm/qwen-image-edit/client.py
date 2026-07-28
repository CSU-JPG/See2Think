import os
import sys
import base64
from openai import OpenAI


# 1. 准备图片转 Base64 的函数
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def main():
    # 使用环境变量来构造 base_url，这样可以和 run 脚本配合
    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", "8000")
    base_url = f"http://{host}:{port}/v1"

    # 检查输入图片是否存在
    for fn in ("input1.jpg", "input2.jpg"):
        if not os.path.isfile(fn):
            print(f"输入图片 '{fn}' 未找到。请将输入图片放在当前目录或修改文件名。")
            sys.exit(2)

    # 2. 读取本地图片
    img1_b64 = encode_image("input1.jpg")
    img2_b64 = encode_image("input2.jpg")

    # 3. 初始化客户端 (指向本地服务)
    client = OpenAI(
        base_url=base_url,
        api_key="EMPTY"
    )

    print(f"正在发送请求到本地 Qwen Server ({base_url})...")

    # 4. 发送请求 (模拟 GPT-4o-V 的格式)
    response = client.chat.completions.create(
        model="Qwen-Image-Edit-2509",
        messages=[
            {
                "role": "user",
                "content": [
                    # 提示词
                    {
                        "type": "text",
                        "text": "make the bear look cute"
                    },
                    # 图片 1
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img1_b64}"
                        }
                    },
                ]
            }
        ],
        temperature=0.1
    )

    # 5. 处理返回结果
    result_content = response.choices[0].message.content

    # 假设服务端返回的是 Base64 图片字符串
    try:
        image_data = base64.b64decode(result_content)
        with open("/storage/v-jinpewang/yansiyu_workspace/See2Think/result_api.png", "wb") as f:
            f.write(image_data)
        print("成功！结果已保存为 result_api.png")
    except Exception as e:
        print("解析返回结果出错:", e)
        print("原始返回:", str(result_content)[:200])


if __name__ == "__main__":
    main()