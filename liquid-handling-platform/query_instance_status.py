

# 数据库连接参数
import psycopg2
from psycopg2 import sql

db_params = {
    'dbname': 'aichem_worker',          # 数据库名称
    'user': 'postgres',                 # 数据库用户名
    'password': 'aichem123!',           # 数据库密码
    'host': '192.168.110.179',          # 数据库主机地址
    'port': '5432'                     # 数据库端口
}

class QueryInstanceStatus:
    @staticmethod
    def check_instance_status(instance_id):
        """检查实例状态"""
        try:
            # 连接到 PostgreSQL 数据库
            conn = psycopg2.connect(**db_params)
            cursor = conn.cursor()

            # 查询语句
            query = sql.SQL("SELECT status FROM task_instance WHERE id = %s").format(
                sql.Identifier('id')
            )
            cursor.execute(query, (instance_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                return -1
        except psycopg2.Error as e:
            print(f"数据库错误: {e}")
            return -1
        finally:
            # 关闭游标和连接
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

if __name__ == '__main__':
    print(QueryInstanceStatus.check_instance_status(1518265754714114))


